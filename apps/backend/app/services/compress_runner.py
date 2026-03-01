import os
import threading
import logging
from app.extensions import db
from app.models.compress_task import CompressTask, CompressStage
from app.core.compression.pipeline import CompressionPipeline

logger = logging.getLogger(__name__)

class CompressTaskRunner:
    @staticmethod
    def run_task(task_id: int):
        """
        Start the compression task in a background thread.
        """
        from flask import current_app
        # Capture the real app object to pass to the thread
        app = current_app._get_current_object()
        thread = threading.Thread(target=CompressTaskRunner._execute_task, args=(app, task_id))
        thread.start()

    @staticmethod
    def _execute_task(app, task_id: int):
        # Create a new app context for the thread
        with app.app_context():
            task = CompressTask.query.get(task_id)
            if not task:
                logger.error(f"Task {task_id} not found")
                return

            # Setup Task Logger
            log_dir = f'/data/workspace/hdap-platform/backend/hdap-platform-backend/data/tasks/{task_id}'
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'stdout.log')
            
            # Create a file handler for this task
            task_file_handler = logging.FileHandler(log_file, mode='w')
            task_file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
            
            # Attach to the root logger or specific loggers used in compression
            # We want to capture logs from app.core.compression.*
            # FIX: Ensure we capture logs from both 'app.core.compression' and 'app.services.compress_runner' (this file)
            # Actually, let's attach to the root 'app' logger to be safe, but filter?
            # Or just attach to both specific loggers we care about.
            
            loggers_to_attach = [
                logging.getLogger('app.core.compression'),
                logging.getLogger('app.services.compress_runner') # For this runner's logs
            ]
            
            for l in loggers_to_attach:
                l.addHandler(task_file_handler)
                l.setLevel(logging.INFO)

            try:
                # Use comp_logger alias for explicit writing if needed, but standard logger.info should work now
                # logger.info uses 'app.services.compress_runner' which we just attached.
                logger.info(f"Starting task {task_id}: {task.name}")
                
                # Update status
                task.status = 'running'
                db.session.commit()
                
                # Initialize and Run Pipeline
                pipeline = CompressionPipeline(task_id)
                pipeline.run()
                
                # Success
                task.status = 'succeeded'
                stage = CompressStage.query.filter_by(task_id=task.id, phase='pruning').first()
                if stage:
                    stage.status = 'succeeded'
                    stage.progress = 100
                db.session.commit()

            except InterruptedError:
                logger.warning(f"Task {task_id} execution aborted.")
                # Ensure status is aborted in DB (it should be, but let's be safe)
                task.status = 'aborted'
                stage = CompressStage.query.filter_by(task_id=task.id, phase='pruning').first()
                if stage:
                    stage.status = 'aborted'
                db.session.commit()
                
            except Exception as e:
                logger.exception(f"Error executing task {task_id}: {e}")
                # Log to file as well via the logger attached
                logger.error(f"Task failed: {e}")
                
                task.status = 'failed'
                stage = CompressStage.query.filter_by(task_id=task.id, phase='pruning').first()
                if stage:
                    stage.status = 'failed'
                db.session.commit()
            finally:
                # Cleanup logger
                for l in loggers_to_attach:
                    l.removeHandler(task_file_handler)
                task_file_handler.close()
