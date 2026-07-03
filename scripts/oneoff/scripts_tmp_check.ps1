$root = "c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app"
Get-ChildItem -Path $root -Recurse -Filter "*.py" |
    Where-Object { $_.Name -ne "__init__.py" -and $_.DirectoryName -notmatch "tests|test_" } |
    ForEach-Object {
        $lines = (Get-Content $_.FullName | Measure-Object -Line).Lines
        $rel = $_.FullName.Substring($root.Length)
        "{0,-6} {1}" -f $lines, $rel
    } | Sort-Object -Descending | Select-Object -First 30
