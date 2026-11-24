$ErrorActionPreference = 'Stop';
cd "d:\Kane Hackathon\frontend";
npm run build;
cd "d:\Kane Hackathon";
$env:TEMP='D:\temp';
$env:TMP='D:\temp';
if (!(Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    pip install pyinstaller;
}
pyinstaller --name TideFlow_Hexactine --add-data "frontend/dist;frontend/dist" --add-data "backend;backend" --hidden-import uvicorn --hidden-import fastapi --hidden-import pydantic --hidden-import starlette --hidden-import py2neo --hidden-import networkx --hidden-import httpx --hidden-import relate --noconfirm launcher.py;
mkdir -Force "d:\Kane Hackathon\submission_package";
Copy-Item -Recurse -Force "d:\Kane Hackathon\dist\TideFlow_Hexactine" "d:\Kane Hackathon\submission_package\";
