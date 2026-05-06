@echo off
echo ========================================================
echo Starting Daily Crawler Pipeline
echo ========================================================

cd /d %~dp0..

echo [1] Running Dispatcher (Crawlers)...
python tools\crawler_dispatcher.py

echo [2] Parsing CDP Data...
python tools\cdp\parse_cdp_data.py

echo [3] Merging to Dashboard...
python merge_file.py

echo [4] Ingesting Data to Unified Parquet...
python ResuMiner\scripts\ingest_all.py

echo [5] Rebuilding Semantic Vector Index...
python ResuMiner\pipeline\build_index.py

echo ========================================================
echo Pipeline Completed!
echo ========================================================
