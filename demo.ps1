# Démo de bout en bout du Copilote Marketing (mode démo, sans clé API).
# Lancement : powershell -ExecutionPolicy Bypass -File demo.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$py = ".\.venv\Scripts\python.exe"

function Step($title) {
    Write-Host ""
    Write-Host "=== $title ===" -ForegroundColor Cyan
}

function Pause-Demo {
    Read-Host "Entrée pour continuer" | Out-Null
}

# Repart d'un état propre (les sorties de démo sont dans out/, ignoré par git)
Remove-Item -Recurse -Force out\posts, out\watch, out\scheduled, out\published, out\images -ErrorAction SilentlyContinue

Step "1. Base de connaissances : ingestion des documents de marque (RAG)"
& $py -m src.cli ingest
Pause-Demo

Step "2. Base de connaissances interrogeable"
& $py -m src.cli ask "Quel est le degré de la Saison Démo ?"
& $py -m src.cli ask "Quel est le prix de la Blonde ?"
Pause-Demo

Step "3. Flux hebdomadaire : veille + 3 brouillons (2 LinkedIn + 1 Instagram) + visuels"
& $py -m src.cli weekly --offline
Pause-Demo

Step "4. Social listening : tendances et mentions des concurrents"
& $py -m src.cli trends --top 8
Pause-Demo

Step "5. Validation humaine (a = approuver, r = rejeter, e = éditer, p = passer, q = quitter)"
& $py -m src.cli list
& $py -m src.cli review

Step "6. Programmation des posts approuvés (calendrier 2 LinkedIn + 1 Instagram / semaine)"
& $py -m src.cli schedule
Pause-Demo

Step "7. Publication des posts arrivés à échéance (simulation dans 30 jours, mode mock)"
& $py -m src.cli publish-due --at (Get-Date).AddDays(30).ToString("yyyy-MM-dd")
& $py -m src.cli list
Pause-Demo

Step "8. Mini-évaluation sur 10 cas"
& $py -m tests.eval

Write-Host ""
Write-Host "Fichiers produits : out\posts, out\images (visuels), out\scheduled, out\published." -ForegroundColor Green
Write-Host "Détail d'un post : .venv\Scripts\python -m src.cli show <id>" -ForegroundColor Green
