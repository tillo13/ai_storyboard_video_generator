# Total start time 
$totalStart = [datetime]::Now

# Array to store individual script times
$scriptTimes = @{}


# Get the directory where the PowerShell script is located
$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Definition

# Function to read the number of runs from GLOBAL_VARIABLES.py
function Get-GlobalVariable {
    param (
        [string]$variableName
    )

    $globalVarsPath = Join-Path $scriptDirectory "GLOBAL_VARIABLES.py"
    $line = Get-Content $globalVarsPath | Select-String -Pattern "^\s*${variableName}\s*=\s*(\d+)" | Select-Object -First 1

    if ($line -match "^\s*${variableName}\s*=\s*(\d+)") {
        return [int]$matches[1]
    } else {
        throw "Variable $variableName not found in $globalVarsPath"
    }
}

# Retrieve the number of runs from GLOBAL_VARIABLES.py
$number_of_runs = Get-GlobalVariable "NUMBER_OF_RUNS"

# Function to run a Python script and log the time taken
function Run-LogPythonScript {
    param (
        [string]$scriptName
    )
    
    $scriptPath = Join-Path $scriptDirectory $scriptName
    
    # Capturing the start timestamp
    $start = [datetime]::Now
    Write-Output "Running ${scriptPath}"
    
    # Run the python script and wait for it to exit
    $process = Start-Process -FilePath "python" -ArgumentList $scriptPath -NoNewWindow -PassThru -Wait

    # Capturing the end timestamp and computing elapsed time
    $end = [datetime]::Now
    $elapsed = $end - $start
    Write-Output "${scriptName} completed in $($elapsed.TotalSeconds) seconds"
    Write-Output "----------------------------------------"

    # Store the time taken for the script
    if (-not $scriptTimes.ContainsKey($scriptName)) {
        $scriptTimes[$scriptName] = 0
    }
    $scriptTimes[$scriptName] += $elapsed.TotalSeconds
}

# Loop through the specified number of runs
for ($i = 1; $i -le $number_of_runs; $i++) {
    Write-Output "`nRun $i of $number_of_runs..."
    
    # Run each script
    Run-LogPythonScript "utilities/archive_utils.py"
    Run-LogPythonScript "1_dream_up_a_story.py"
    Run-LogPythonScript "2_build_out_chapters.py"
    Run-LogPythonScript "3_summarize_chapters_add_ai_prompts.py"
    Run-LogPythonScript "4_create_images_from_ai_prompts.py"
    Run-LogPythonScript "5_create_movie.py"
    Run-LogPythonScript "6_create_mosaic.py"
    Run-LogPythonScript "7_zoompan_movie.py"
    Run-LogPythonScript "8_add_ffmpeg_subtitles.py"
    Run-LogPythonScript "9_create_voiceover.py"
}

# Total end time
$totalEnd = [datetime]::Now
$totalElapsed = $totalEnd - $totalStart

# Display summary
Write-Output "`n=== SUMMARY ==="
foreach ($script in $scriptTimes.Keys) {
    Write-Output "${script}: $($scriptTimes[$script]) seconds"
}
Write-Output "Total runs: $number_of_runs"
Write-Output "Total time: $($totalElapsed.TotalSeconds) seconds."