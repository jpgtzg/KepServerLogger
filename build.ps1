Set-Location "$PSScriptRoot\extractors"
uv run pyinstaller extractor.spec --noconfirm
