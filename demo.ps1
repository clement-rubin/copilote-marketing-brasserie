# Démo de bout en bout du Copilote Marketing (mode démo, sans clé API).
# Lancement : .\demo.ps1   (depuis le dossier du projet)

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
Remove-Item -Recurse -Force out\posts, out\watch, out\scheduled -ErrorAction SilentlyContinue

Step "1. Ingestion des documents de marque dans ChromaDB"
& $py -m src.cli ingest
Pause-Demo

Step "2. Veille RSS sur le flux fictif (résumé + déduplication)"
& $py -m src.cli watch --offline
Pause-Demo

Step "3. Génération : 3 posts LinkedIn + 1 Instagram à partir du 1er article"
& $py -m src.cli generate --articles 1
Pause-Demo

Step "4. File de validation humaine (tout est en brouillon)"
& $py -m src.cli list
Write-Host "Validation interactive : a = approuver, r = rejeter, e = éditer, p = passer, q = quitter" -ForegroundColor Yellow
& $py -m src.cli review

Step "5. Programmation des posts approuvés (2 LinkedIn + 1 Instagram / semaine)"
& $py -m src.cli schedule
& $py -m src.cli list
Pause-Demo

Step "6. Mini-évaluation sur 10 cas"
& $py -m tests.eval

Write-Host ""
Write-Host "Fichiers produits : out\posts, out\scheduled. Détail d'un post : python -m src.cli show <id>" -ForegroundColor Green
