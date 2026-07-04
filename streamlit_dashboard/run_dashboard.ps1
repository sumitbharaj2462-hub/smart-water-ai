$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

Set-Location $root
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8501
