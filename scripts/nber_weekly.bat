@echo off
:: NBER Weekly Paper Fetcher — runs via Windows Task Scheduler
:: Fetches papers, saves log + summary, optionally downloads PDFs

cd /d "C:\Users\xudin\OneDrive\IO course\clo-author"
python scripts\nber_weekly.py --all-details --download >> "master_supporting_docs\nber\log\scheduler.log" 2>&1
