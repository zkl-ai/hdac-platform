import paramiko
from flask import request
from flask_socketio import emit, disconnect
from app.extensions import socketio, db
from app.models.device import Device
import threading

ssh_sessions = {}

@socketio.on('connect', namespace='/ssh')
def connect():
    pass

@socketio.on('disconnect', namespace='/ssh')
def disconnect_handler():
    sid = request.sid
    if sid in ssh_sessions:
        session = ssh_sessions.pop(sid)
        try:
            session['ssh'].close()
        except:
            pass

@socketio.on('start_ssh', namespace='/ssh')
def start_ssh(data):
    device_ip = data.get('ip')
    if not device_ip:
        emit('output', {'data': 'Error: No IP provided\r\n'})
        disconnect()
        return

    # Ensure we are in app context if needed, but SQLAlchemy objects bound to session might need care.
    # Here we just query fresh.
    device = Device.query.filter_by(ip=device_ip).first()
    
    if not device:
        emit('output', {'data': 'Error: Device not found\r\n'})
        disconnect()
        return

    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            device.ip,
            port=device.port or 22,
            username=device.username,
            password=device.password,
            timeout=10
        )
        
        channel = ssh.invoke_shell(term='xterm', width=80, height=24)
        
        ssh_sessions[request.sid] = {'ssh': ssh, 'channel': channel}
        
        socketio.start_background_task(target=listen_to_ssh, sid=request.sid, channel=channel)
        
        emit('output', {'data': f'Connected to {device.ip}...\r\n'})
        
    except Exception as e:
        emit('output', {'data': f'Connection failed: {str(e)}\r\n'})
        disconnect()

def listen_to_ssh(sid, channel):
    while True:
        try:
            if channel.recv_ready():
                data = channel.recv(1024).decode('utf-8', errors='ignore')
                socketio.emit('output', {'data': data}, room=sid, namespace='/ssh')
            elif channel.exit_status_ready():
                break
            else:
                socketio.sleep(0.01)
        except Exception:
            break
            
    # Cleanup if loop exits
    socketio.emit('output', {'data': '\r\nConnection closed.\r\n'}, room=sid, namespace='/ssh')
    # We don't forcefully disconnect socket here to allow user to see message, 
    # but we could send a special event.

@socketio.on('input', namespace='/ssh')
def handle_input(data):
    sid = request.sid
    if sid in ssh_sessions:
        channel = ssh_sessions[sid]['channel']
        try:
            channel.send(data['data'])
        except:
            pass

@socketio.on('resize', namespace='/ssh')
def handle_resize(data):
    sid = request.sid
    if sid in ssh_sessions:
        channel = ssh_sessions[sid]['channel']
        rows = data.get('rows', 24)
        cols = data.get('cols', 80)
        try:
            channel.resize_pty(width=cols, height=rows)
        except:
            pass
