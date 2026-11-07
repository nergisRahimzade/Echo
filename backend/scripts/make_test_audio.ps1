# Generates clear test recordings with the built-in Windows voices (no internet needed).
# Usage (from backend/):  powershell -ExecutionPolicy Bypass -File scripts/make_test_audio.ps1 [-OutDir tests/audio]
# Each file is named after its language and phrase id; labels.json maps file -> correct text.
# One custom sentence:     ... -Text "Pamuk nerede?" -Lang tr -Out pamuk.wav
param([string]$OutDir = "tests/audio", [string]$Text = "", [string]$Lang = "tr", [string]$Out = "")

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]
function Await($op, [Type]$type) {
    $task = $asTaskGeneric.MakeGenericMethod($type).Invoke($null, @($op))
    $task.Wait(-1) | Out-Null
    $task.Result
}
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null

function Save-Speech([string]$sentence, [string]$culture, [string]$path) {
    $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -eq $culture } | Select-Object -First 1
    if (-not $voice) { throw "No $culture voice installed" }
    $s = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
    $s.Voice = $voice
    $stream = Await ($s.SynthesizeTextToStreamAsync($sentence)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
    Await ($reader.LoadAsync([uint32]$stream.Size)) ([uint32]) | Out-Null
    $bytes = New-Object byte[] $stream.Size
    $reader.ReadBytes($bytes)
    [IO.File]::WriteAllBytes($path, $bytes)
}

if ($Text) {
    $culture = @{ tr = "tr-TR"; en = "en-US" }[$Lang]
    Save-Speech $Text $culture ([IO.Path]::GetFullPath($Out))
    Write-Host "wrote $Out"
    exit 0
}

$repo = Resolve-Path (Join-Path $PSScriptRoot "..\..")
New-Item -ItemType Directory -Force $OutDir | Out-Null
$labels = [ordered]@{}
$synth = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer

foreach ($lang in @("tr", "en")) {
    $culture = @{ tr = "tr-TR"; en = "en-US" }[$lang]
    $voice = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -eq $culture } | Select-Object -First 1
    if (-not $voice) { Write-Warning "No $culture voice installed; skipping $lang"; continue }
    $synth.Voice = $voice
    $phrases = Get-Content -Raw -Encoding UTF8 (Join-Path $repo "phrases\$lang.json") | ConvertFrom-Json
    foreach ($p in $phrases) {
        $stream = Await ($synth.SynthesizeTextToStreamAsync($p.text)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
        $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
        Await ($reader.LoadAsync([uint32]$stream.Size)) ([uint32]) | Out-Null
        $bytes = New-Object byte[] $stream.Size
        $reader.ReadBytes($bytes)
        $name = "$lang-$($p.id).wav"
        [IO.File]::WriteAllBytes((Join-Path (Resolve-Path $OutDir) $name), $bytes)
        $labels[$name] = @{ text = $p.text; language = $lang }
    }
    Write-Host "$lang : $($phrases.Count) files with voice $($voice.DisplayName)"
}
$labels | ConvertTo-Json -Depth 3 | Out-File -Encoding utf8 (Join-Path $OutDir "labels.json")
