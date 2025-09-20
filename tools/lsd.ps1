# List files sorted by date (newest first) with full paths
# Usage: .\lsd.ps1 or just lsd if in PATH
# Script name is a joke, y'all! :-)

param(
    [string]$Path = ".",
    [switch]$Recurse,
    [string]$Filter = "*"
)

if ($Recurse) {
    Get-ChildItem -Path $Path -Filter $Filter -Recurse |
        Sort-Object LastWriteTime -Descending |
        Select-Object FullName, LastWriteTime
} else {
    Get-ChildItem -Path $Path -Filter $Filter |
        Sort-Object LastWriteTime -Descending |
        Select-Object FullName, LastWriteTime
}