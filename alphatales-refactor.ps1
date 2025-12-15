# AlphaTales Refactor Agent - Direct Launcher (PowerShell)
# This bypasses pip install and runs directly from source

$env:PYTHONPATH = "P:\Source\refacta\src;$env:PYTHONPATH"
& C:\Python312\python.exe -c "from refactor_agent.cli import main; main()" $args
