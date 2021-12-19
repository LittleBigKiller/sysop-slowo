from flask import Flask
app = Flask(__name__)

import psutil
import subprocess


def checkIfProcessRunning(processName):
    '''
    Check if there is any running process that contains the given name processName.
    '''
    #Iterate over the all the running process
    p_list = []
    for proc in psutil.process_iter():
        try:
            # Check if process name contains the given name string.
            name = map(lambda x: x.lower(), proc.cmdline())
            if processName.lower() in name:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


@app.route("/")
def hello():
    return "Hello World!"


@app.route("/test")
def test():
    # return "TEST"
    if checkIfProcessRunning("sysop-srv"):
        return "was running"
    else:
        subprocess.call("./start.sh", shell=True)
        return "is now running"
        


if __name__ == "__main__":
    app.run()

