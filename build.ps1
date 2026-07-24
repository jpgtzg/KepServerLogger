param (
    [switch]$certgen
)

if ($certgen) {
    Push-Location .\utils\certgen
    uv run pyinstaller certgen.spec --noconfirm
    Pop-Location
}

Push-Location .\extractor
uv run pyinstaller extractor.spec --noconfirm
Pop-Location
