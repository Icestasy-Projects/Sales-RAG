# Icestasy RAG Demo — launch script
# Run from the icestasy-rag-demo folder:  .\run.ps1

$env:SUPABASE_URL         = "https://acngdpcpxburkzqxjpbf.supabase.co"
$env:SUPABASE_KEY         = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjbmdkcGNweGJ1cmt6cXhqcGJmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3OTg4MjcsImV4cCI6MjA5NzM3NDgyN30.t2XuMvFL5iyGeWkERJrTFPmJdNMb48gCUcn8Z0j5bsM"
$env:SUPABASE_SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFjbmdkcGNweGJ1cmt6cXhqcGJmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MTc5ODgyNywiZXhwIjoyMDk3Mzc0ODI3fQ.dZHfewnIMa8GV4aPMYXKdOPGSWz00g33u3_QDCjAC2g"

# Paste your free Groq key here — get one at https://console.groq.com
$env:GROQ_API_KEY         = "your_groq_api_key_here"

Write-Host "Starting Icestasy RAG Demo on http://localhost:5000" -ForegroundColor Green
python app.py
