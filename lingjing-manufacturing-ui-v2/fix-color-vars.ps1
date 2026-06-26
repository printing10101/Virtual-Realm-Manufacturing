$pagesDir = 'c:\Users\Lenovo\Desktop\灵境制造（上线版）\lingjing-manufacturing-ui-v2\pages'

$colorMappings = @'

  /* ===== COLOR ALIAS LAYER (--color-*) ===== */
  --color-bg-50: var(--background-50);
  --color-bg-100: var(--background-100);
  --color-bg-200: var(--background-200);
  --color-bg-300: var(--background-300);
  --color-text-primary: var(--text-800);
  --color-text-secondary: var(--text-500);
  --color-text-tertiary: var(--text-400);
  --color-text-muted: var(--text-400);
  --color-text-placeholder: var(--text-300);
  --color-text-inverse: var(--background-50);
  --color-border-subtle: var(--background-300);
  --color-border-default: var(--background-300);
  --color-border-strong: var(--background-500);
  --color-border-focus: var(--brand-500);
  --color-primary-50: var(--brand-50);
  --color-primary-100: var(--brand-100);
  --color-primary-200: var(--brand-200);
  --color-primary-300: var(--brand-300);
  --color-primary-400: var(--brand-400);
  --color-primary-500: var(--brand-500);
  --color-primary-600: var(--brand-600);
  --color-primary-700: var(--brand-700);
  --color-primary-800: var(--brand-800);
  --color-brand-400: var(--brand-400);
  --color-brand-500: var(--brand-500);
  --color-brand-800: var(--brand-800);
'@

$files = Get-ChildItem -Path $pagesDir -Filter '*.html'
foreach ($file in $files) {
    $content = Get-Content -Path $file.FullName -Raw -Encoding UTF8
    if ($content -match '--color-bg-50:') {
        Write-Host "SKIP: $($file.Name)"
        continue
    }
    $marker = '--spacing: 0.24rem;'
    if ($content -match [regex]::Escape($marker)) {
        $insertPoint = $content.IndexOf($marker) + $marker.Length
        $newContent = $content.Substring(0, $insertPoint) + $colorMappings + $content.Substring($insertPoint)
        Set-Content -Path $file.FullName -Value $newContent -Encoding UTF8 -NoNewline
        Write-Host "FIXED: $($file.Name)"
    } else {
        Write-Host "WARN: $($file.Name)"
    }
}
