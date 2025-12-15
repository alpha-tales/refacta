@echo off
REM AlphaTales Refactor Agent - Direct Launcher
REM This bypasses pip install and runs directly from source

set PYTHONPATH=P:\Source\refacta\src;%PYTHONPATH%
C:\Python312\python.exe -c "from refactor_agent.cli import main; main()" %*
