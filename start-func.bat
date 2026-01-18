@echo off
chcp 65001
cd /d "%~dp0platforms\azure"
func start --python
