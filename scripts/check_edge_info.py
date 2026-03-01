
import paramiko

def check_edge_info():
    hostname = "10.16.62.48"
    username = "root"
    password = "coding@password01"
    
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(hostname, username=username, password=password)
        
        commands = [
            "cat /etc/os-release",
            "cat /etc/nv_tegra_release",
            "uname -a",
            "cat /proc/cpuinfo | grep 'model name' | uniq"
        ]
        
        for cmd in commands:
            print(f"--- Executing: {cmd} ---")
            stdin, stdout, stderr = client.exec_command(cmd)
            print(stdout.read().decode())
            err = stderr.read().decode()
            if err:
                print(f"Error: {err}")
                
        client.close()
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    check_edge_info()
