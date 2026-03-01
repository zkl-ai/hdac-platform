import unittest
from unittest.mock import MagicMock, patch
import json
import sys
import os

# Add app path to sys.path
sys.path.append('/data/workspace/hdap-platform/backend/hdap-platform-backend')

from app.services.cluster_service import ClusterService

class TestClusterService(unittest.TestCase):
    @patch('paramiko.SSHClient')
    def test_profile_device_real_success(self, mock_ssh_client):
        # Setup Mock
        mock_ssh = MagicMock()
        mock_ssh_client.return_value = mock_ssh
        
        # Mock exec_command behavior
        # We expect 3 calls:
        # 1. mkdir -p ...
        # 2. docker run ... (ensure container)
        # 3. docker exec ... (run profile)
        
        # Setup stdout/stderr mocks
        mock_stdout_mkdir = MagicMock()
        mock_stdout_mkdir.channel.recv_exit_status.return_value = 0
        
        mock_stdout_docker_run = MagicMock()
        mock_stdout_docker_run.channel.recv_exit_status.return_value = 0
        
        mock_stdout_profile = MagicMock()
        mock_stdout_profile.channel.recv_exit_status.return_value = 0
        mock_stdout_profile.read.return_value = json.dumps([10.5, 11.2, 10.8]).encode('utf-8')
        
        mock_stderr = MagicMock()
        mock_stderr.read.return_value = b""
        
        # Configure side_effect for exec_command
        mock_ssh.exec_command.side_effect = [
            (None, mock_stdout_mkdir, mock_stderr),       # mkdir
            (None, mock_stdout_docker_run, mock_stderr),  # docker run check
            (None, mock_stdout_profile, mock_stderr)      # docker exec
        ]
        
        # Mock SFTP
        mock_sftp = MagicMock()
        mock_ssh.open_sftp.return_value = mock_sftp
        
        # Test Data
        device = MagicMock()
        device.ip = "192.168.1.100"
        device.username = "user"
        device.password = "pass"
        device.type = "Jetson Xavier NX" # Should trigger nx1.0 tag
        
        local_model = "/tmp/fake_model.pth"
        local_profiler = "/tmp/fake_profiler.py"
        
        # Create dummy files
        with open(local_model, 'w') as f: f.write("dummy")
        with open(local_profiler, 'w') as f: f.write("dummy")
            
        try:
            # Run
            result = ClusterService._profile_device_real(device, local_model, local_profiler, rates=[0]*56)
            
            # Verify
            print("\n--- Test Result ---")
            print(f"Result: {result}")
            self.assertEqual(result, [10.5, 11.2, 10.8])
            
            # Verify Docker Command used correct tag
            calls = mock_ssh.exec_command.call_args_list
            docker_run_cmd = calls[1][0][0]
            print(f"Docker Run Command:\n{docker_run_cmd}")
            self.assertIn("hampenv:nx1.0", docker_run_cmd)
            self.assertIn("--entrypoint /bin/bash", docker_run_cmd)
            self.assertIn('tail -f /dev/null', docker_run_cmd)
            
            print("Test Passed: Logic flow is correct.")
            
        finally:
            if os.path.exists(local_model): os.remove(local_model)
            if os.path.exists(local_profiler): os.remove(local_profiler)

if __name__ == '__main__':
    unittest.main()
