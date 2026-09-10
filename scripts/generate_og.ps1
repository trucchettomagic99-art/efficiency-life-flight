Add-Type -AssemblyName System.Drawing

$width = 1200
$height = 630

$bmp = New-Object System.Drawing.Bitmap($width, $height)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::HighQuality
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::ClearTypeGridFit
$g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

# 1. Background: Deep navy/black void #03070e
$bgBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 3, 7, 14))
$g.FillRectangle($bgBrush, 0, 0, $width, $height)

# 2. Ambient radial glow on right side (behind globe)
$path = New-Object System.Drawing.Drawing2D.GraphicsPath
$path.AddEllipse(650, 60, 600, 600)
$pgb = New-Object System.Drawing.Drawing2D.PathGradientBrush($path)
$pgb.CenterColor = [System.Drawing.Color]::FromArgb(45, 43, 135, 255)
$pgb.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 3, 7, 14))
$g.FillEllipse($pgb, 650, 60, 600, 600)

# 3. Subtle grid lines / tech background accents
$gridPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(18, 255, 255, 255), 1)
for ($x = 60; $x -lt $width; $x += 80) { $g.DrawLine($gridPen, $x, 0, $x, $height) }
for ($y = 60; $y -lt $height; $y += 70) { $g.DrawLine($gridPen, 0, $y, $width, $y) }

# 4. Top Header Rail
# Logo icon
$iconPath = "c:\Users\Francesco\efficiency-life-flight\public\icon-512.png"
if (Test-Path $iconPath) {
    $iconImg = [System.Drawing.Image]::FromFile($iconPath)
    $g.DrawImage($iconImg, 64, 42, 44, 44)
    $iconImg.Dispose()
}

$fontLogoBold = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Bold)
$fontLogoReg  = New-Object System.Drawing.Font("Segoe UI", 18, [System.Drawing.FontStyle]::Regular)
$fontMonoSm   = New-Object System.Drawing.Font("Consolas", 11, [System.Drawing.FontStyle]::Bold)
$fontMonoXs   = New-Object System.Drawing.Font("Consolas", 9, [System.Drawing.FontStyle]::Regular)
$fontH1       = New-Object System.Drawing.Font("Segoe UI", 36, [System.Drawing.FontStyle]::Bold)
$fontBody     = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Regular)
$fontStatNum  = New-Object System.Drawing.Font("Segoe UI", 26, [System.Drawing.FontStyle]::Bold)
$fontStatLbl  = New-Object System.Drawing.Font("Segoe UI", 11, [System.Drawing.FontStyle]::Regular)

$brushWhite = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
$brushMuted = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 140, 160, 185))
$brushBlue  = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 43, 135, 255))
$brushCyan  = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 77, 226, 255))

# Brand text
$g.DrawString("Efficiency ", $fontLogoBold, $brushWhite, 118, 45)
$g.DrawString("Life", $fontLogoReg, $brushWhite, 258, 45)

# Module badge "FLIGHT"
$badgePen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(255, 43, 135, 255), 1.5)
$badgeBg  = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(40, 43, 135, 255))
$g.FillRectangle($badgeBg, 320, 50, 72, 26)
$g.DrawRectangle($badgePen, 320, 50, 72, 26)
$g.DrawString("FLIGHT", $fontMonoSm, $brushCyan, 328, 54)

# Other modules in header
$g.DrawString("Stay", $fontMonoSm, $brushMuted, 420, 54)
$g.DrawString("Rail", $fontMonoSm, $brushMuted, 480, 54)
$g.DrawString("Drive", $fontMonoSm, $brushMuted, 535, 54)
$g.DrawString("Energy", $fontMonoSm, $brushMuted, 600, 54)

# Top right live tag
$liveBorder = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(80, 77, 226, 255), 1)
$liveBg = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(25, 77, 226, 255))
$g.FillRectangle($liveBg, 970, 48, 166, 28)
$g.DrawRectangle($liveBorder, 970, 48, 166, 28)
$dotBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 77, 226, 255))
$g.FillEllipse($dotBrush, 982, 58, 8, 8)
$g.DrawString("LIVE RADAR · 2026", $fontMonoXs, $brushCyan, 998, 55)

# 5. Left Hero Section
# Eyebrow
$g.DrawString("TARIFFA REALE · VOLI DIRETTI · 1.300+ ORIGINI NEL MONDO", $fontMonoSm, $brushCyan, 64, 140)

# Main Title
$g.DrawString("NON SCEGLIERE DOVE.", $fontH1, $brushWhite, 60, 175)
$g.DrawString("SCEGLI QUANTO LONTANO.", $fontH1, $brushBlue, 60, 238)

# Lede
$g.DrawString("Il motore di ricerca che trova dove volare con il tuo budget", $fontBody, $brushWhite, 64, 324)
$g.DrawString("al miglior rapporto distanza-prezzo (km per euro).", $fontBody, $brushMuted, 64, 354)

# 6. Bottom Stats Cards
$statY = 445
$cardPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(40, 255, 255, 255), 1)
$cardBg  = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(18, 255, 255, 255))

$stats = @(
    @{ Val = "1.329"; Lbl = "Aeroporti origine"; X = 64 },
    @{ Val = "21.900+"; Lbl = "Tariffe osservate"; X = 230 },
    @{ Val = "36"; Lbl = "Lingue supportate"; X = 415 },
    @{ Val = "Km / €"; Lbl = "Metodo di ranking"; X = 560 }
)

foreach ($s in $stats) {
    $g.FillRectangle($cardBg, $s.X, $statY, 145, 115)
    $g.DrawRectangle($cardPen, $s.X, $statY, 145, 115)
    $g.DrawString($s.Val, $fontStatNum, $brushWhite, ($s.X + 12), ($statY + 16))
    $g.DrawString($s.Lbl, $fontStatLbl, $brushMuted, ($s.X + 12), ($statY + 68))
}

# 7. Right Side: Orthographic Globe & Flight Arcs
$globeCx = 960
$globeCy = 355
$globeR  = 180

# Outer sphere ring
$spherePen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(70, 77, 226, 255), 1.5)
$g.DrawEllipse($spherePen, ($globeCx - $globeR), ($globeCy - $globeR), ($globeR * 2), ($globeR * 2))

# Latitude parallels
$gridSpherePen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(35, 77, 226, 255), 1)
$g.DrawLine($gridSpherePen, ($globeCx - $globeR), $globeCy, ($globeCx + $globeR), $globeCy)
$g.DrawEllipse($gridSpherePen, ($globeCx - $globeR * 0.95), ($globeCy - 65), ($globeR * 1.9), 130)
$g.DrawEllipse($gridSpherePen, ($globeCx - $globeR * 0.8), ($globeCy - 120), ($globeR * 1.6), 80)
$g.DrawEllipse($gridSpherePen, ($globeCx - $globeR * 0.8), ($globeCy + 40), ($globeR * 1.6), 80)

# Meridian arcs
$g.DrawLine($gridSpherePen, $globeCx, ($globeCy - $globeR), $globeCx, ($globeCy + $globeR))
$g.DrawEllipse($gridSpherePen, ($globeCx - 70), ($globeCy - $globeR), 140, ($globeR * 2))
$g.DrawEllipse($gridSpherePen, ($globeCx - 130), ($globeCy - $globeR), 260, ($globeR * 2))

# Hub and flight arcs
$hubX = $globeCx - 30
$hubY = $globeCy - 40

$arcPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(180, 43, 135, 255), 2)
$dests = @(
    @{ X = $globeCx + 110; Y = $globeCy - 80; CtrX = $globeCx + 40; CtrY = $globeCy - 110; DotCol = [System.Drawing.Color]::FromArgb(255, 77, 226, 255) },
    @{ X = $globeCx + 80;  Y = $globeCy + 70; CtrX = $globeCx + 50; CtrY = $globeCy + 20;  DotCol = [System.Drawing.Color]::FromArgb(255, 77, 226, 255) },
    @{ X = $globeCx - 110; Y = $globeCy + 60; CtrX = $globeCx - 90; CtrY = $globeCy;       DotCol = [System.Drawing.Color]::FromArgb(255, 77, 226, 255) },
    @{ X = $globeCx - 90;  Y = $globeCy - 100; CtrX = $globeCx - 70; CtrY = $globeCy - 90; DotCol = [System.Drawing.Color]::FromArgb(255, 255, 100, 100) },
    @{ X = $globeCx + 130; Y = $globeCy - 10; CtrX = $globeCx + 60; CtrY = $globeCy - 50; DotCol = [System.Drawing.Color]::FromArgb(255, 77, 226, 255) },
    @{ X = $globeCx + 40;  Y = $globeCy - 130; CtrX = $globeCx;     CtrY = $globeCy - 120; DotCol = [System.Drawing.Color]::FromArgb(255, 77, 226, 255) }
)

foreach ($d in $dests) {
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddBezier($hubX, $hubY, $d.CtrX, $d.CtrY, $d.CtrX, $d.CtrY, $d.X, $d.Y)
    $g.DrawPath($arcPen, $p)
    $p.Dispose()

    # Destination dot
    $b = New-Object System.Drawing.SolidBrush($d.DotCol)
    $g.FillEllipse($b, ($d.X - 5), ($d.Y - 5), 10, 10)
    $b.Dispose()
}

# Hub center dot (origin)
$hubBrushWhite = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::White)
$hubBrushRing = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(200, 255, 75, 75), 2.5)
$g.DrawEllipse($hubBrushRing, ($hubX - 8), ($hubY - 8), 16, 16)
$g.FillEllipse($hubBrushWhite, ($hubX - 4), ($hubY - 4), 8, 8)

# 8. Floating Glass Deal Card
$cardX = 730
$cardY = 455
$cardW = 410
$cardH = 105

$glassBg = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(235, 8, 16, 30))
$glassBorder = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(120, 77, 226, 255), 1.5)
$g.FillRectangle($glassBg, $cardX, $cardY, $cardW, $cardH)
$g.DrawRectangle($glassBorder, $cardX, $cardY, $cardW, $cardH)

# Deal content inside floating card
$fontCardH = New-Object System.Drawing.Font("Segoe UI", 13, [System.Drawing.FontStyle]::Bold)
$fontCardV = New-Object System.Drawing.Font("Segoe UI", 15, [System.Drawing.FontStyle]::Bold)
$fontCardM = New-Object System.Drawing.Font("Consolas", 10, [System.Drawing.FontStyle]::Regular)

$g.DrawString("MILANO (BGY) → LISBONA (LIS)", $fontCardH, $brushWhite, ($cardX + 16), ($cardY + 14))
$g.DrawString("3.940 km A/R · Diretto", $fontCardM, $brushMuted, ($cardX + 16), ($cardY + 40))
$g.DrawString("38 €", $fontCardV, $brushCyan, ($cardX + 16), ($cardY + 64))

# Efficiency score pill in card
$scorePillBg = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(40, 43, 135, 255))
$scorePillBorder = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(200, 43, 135, 255), 1)
$g.FillRectangle($scorePillBg, ($cardX + 230), ($cardY + 58), 165, 32)
$g.DrawRectangle($scorePillBorder, ($cardX + 230), ($cardY + 58), 165, 32)
$fontScore = New-Object System.Drawing.Font("Consolas", 11, [System.Drawing.FontStyle]::Bold)
$g.DrawString("103,7 km/€ · 98/100", $fontScore, $brushWhite, ($cardX + 236), ($cardY + 66))

# Clean up
$g.Dispose()

$targetPath = "c:\Users\Francesco\efficiency-life-flight\public\og.png"
$bmp.Save($targetPath, [System.Drawing.Imaging.ImageFormat]::Png)
$bmp.Dispose()
Write-Output "Successfully generated $targetPath"
