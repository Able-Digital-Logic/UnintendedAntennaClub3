<#
    fetch_datasheets.ps1
    RFVD_SENSOR_BOARD Rev 1 - datasheet collector

    Downloads the datasheet of every active, protection, magnetic and connector
    part on the board into this folder, named by reference designator.

    Written 2026-09-06 alongside pcb_initial_review.md.
    The review session could not download these directly: the University egress
    proxy returns 403 for ti.com and analog.com. Run this on your own machine.

    Usage (from PowerShell, in this folder):
        .\fetch_datasheets.ps1

    Re-running skips files that already downloaded successfully.
#>

$ErrorActionPreference = 'Continue'
$ProgressPreference    = 'SilentlyContinue'   # much faster downloads

$parts = @(
    # --- Integrated circuits ---
    @{ N='U1_ADL5511.pdf';          U='https://www.analog.com/media/en/technical-documentation/data-sheets/ADL5511.pdf';  D='ADL5511 RF envelope/RMS detector' }
    @{ N='U2_U12_OPA2320.pdf';      U='https://www.ti.com/lit/ds/symlink/opa2320-q1.pdf';                                 D='OPA2320A-Q1 precision op-amp' }
    @{ N='U3_REF5030.pdf';          U='https://www.ti.com/lit/ds/symlink/ref50.pdf';                                      D='REF50xx 3.0V reference' }
    @{ N='U4_LT3045.pdf';           U='https://www.analog.com/media/en/technical-documentation/data-sheets/LT3045.pdf';   D='LT3045 ultralow-noise LDO' }
    @{ N='U5_LMR43620.pdf';         U='https://www.ti.com/lit/ds/symlink/lmr43620.pdf';                                   D='LMR436x0 buck  << SEE FINDING F-01' }
    @{ N='U6_STM32H743VI.pdf';      U='https://www.st.com/resource/en/datasheet/stm32h743vi.pdf';                         D='STM32H743VI MCU' }
    @{ N='U6_STM32H743_RM0433.pdf'; U='https://www.st.com/resource/en/reference_manual/rm0433-stm32h742-stm32h743753-and-stm32h750-value-line-advanced-armbased-32bit-mcus-stmicroelectronics.pdf'; D='STM32H7 reference manual' }
    @{ N='U7_TMP117.pdf';           U='https://www.ti.com/lit/ds/symlink/tmp117.pdf';                                     D='TMP117 temperature sensor' }
    @{ N='U9_TLV809E.pdf';          U='https://www.ti.com/lit/ds/symlink/tlv803e.pdf';                                    D='TLV803E/809E/810E supervisor' }
    @{ N='U10_TPS2553.pdf';         U='https://www.ti.com/lit/ds/symlink/tps2553.pdf';                                    D='TPS2553 current-limit switch' }
    @{ N='U11_SN74LVC1G17.pdf';     U='https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf';                                D='SN74LVC1G17 Schmitt buffer' }
    @{ N='U13_APS6404L.pdf';        U='https://www.mouser.com/datasheet/2/1127/APM_PSRAM_QSPI_APS6404L_3SQN_v2_3_PKG-1954905.pdf'; D='APS6404L QSPI PSRAM' }

    # --- Protection / discrete / magnetic ---
    @{ N='D1_PESD2V5Y1BSF.pdf';     U='https://assets.nexperia.com/documents/data-sheet/PESD2V5Y1BSF.pdf';                D='PESD2V5Y1BSF 0.3pF RF TVS' }
    @{ N='D2_PMEG6030EP.pdf';       U='https://assets.nexperia.com/documents/data-sheet/PMEG6030EP.pdf';                  D='PMEG6030EP 60V 3A Schottky' }
    @{ N='D7_TPD1E10B06.pdf';       U='https://www.ti.com/lit/ds/symlink/tpd1e10b06.pdf';                                 D='TPD1E10B06 trigger ESD' }
    @{ N='D8-D14_PESD5V0U1UL.pdf';  U='https://assets.nexperia.com/documents/data-sheet/PESD5V0U1UL.pdf';                 D='PESD5V0U1UL SD-card ESD' }
    @{ N='F1_MF-MSMF110.pdf';       U='https://www.bourns.com/docs/product-datasheets/mfmsmf.pdf';                        D='Bourns MF-MSMF PTC fuse' }
    @{ N='FB1_BLM18AG601SN1D.pdf';  U='https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/BLM18AG601SN1.pdf';     D='Murata 600R ferrite bead' }
    @{ N='L1_XGL5030.pdf';          U='https://www.coilcraft.com/getmedia/e64ac115-95f2-45c7-b798-1b3769b91583/xgl5030.pdf'; D='Coilcraft XGL5030  << SEE F-13, F-15' }
    @{ N='L1_XAL5030_footprint.pdf';U='https://www.coilcraft.com/getmedia/f7d1b1b0-2f9f-4b21-a1b0-1f1b5d0b1a1a/xal50xx.pdf'; D='Coilcraft XAL50xx (compare land pattern)' }
    @{ N='D3_LTST-C190KGKT.pdf';    U='https://optoelectronics.liteon.com/upload/download/DS22-2000-160/LTST-C190KGKT.pdf'; D='Lite-On green LED' }

    # --- Connectors, switches, oscillator ---
    @{ N='Y1_ASE_oscillator.pdf';   U='https://abracon.com/Oscillators/ASE.pdf';                                          D='Abracon ASE 8MHz oscillator' }
    @{ N='J1_UFL-R-SMT-1.pdf';      U='https://www.hirose.com/product/document?clcode=CL0331&productname=U.FL-R-SMT-1(10)&series=U.FL&documenttype=Catalog&lang=en&documentid=D31727_en'; D='Hirose U.FL receptacle' }
    @{ N='J4_DM3AT-SF-PEJM5.pdf';   U='https://www.hirose.com/product/document?clcode=CL0545&productname=DM3AT-SF-PEJM5&series=DM3&documenttype=2DDrawing&lang=en&documentid=D34686_en'; D='Hirose microSD socket' }
    @{ N='J7_031-5539.pdf';         U='https://www.amphenolrf.com/media/catalog/product/pdf/031-5539.pdf';                D='Amphenol BNC vertical' }
    @{ N='SW1-3_B3U-1000P.pdf';     U='https://omronfs.omron.com/en_US/ecb/products/pdf/en-b3u.pdf';                      D='Omron B3U tactile switch' }
    @{ N='J2_B2B-PH-K-S.pdf';       U='https://www.jst-mfg.com/product/pdf/eng/ePH.pdf';                                  D='JST PH battery connector' }
)

Write-Host ""
Write-Host "RFVD_SENSOR_BOARD Rev 1 - datasheet download" -ForegroundColor Cyan
Write-Host ("=" * 62)
Write-Host ("{0} datasheets queued" -f $parts.Count)
Write-Host ""

$ok = 0; $skip = 0; $fail = @()

foreach ($p in $parts) {
    $name = $p.N
    if ((Test-Path $name) -and ((Get-Item $name).Length -gt 20000)) {
        Write-Host ("  SKIP  {0,-30} already present" -f $name) -ForegroundColor DarkGray
        $skip++
        continue
    }
    try {
        Invoke-WebRequest -Uri $p.U -OutFile $name -TimeoutSec 90 -MaximumRedirection 10 `
            -UserAgent 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)' -ErrorAction Stop
        $size = (Get-Item $name).Length
        if ($size -lt 20000) {
            Remove-Item $name -Force -ErrorAction SilentlyContinue
            throw "response too small ($size bytes) - probably an error page"
        }
        Write-Host ("  OK    {0,-30} {1,6:N0} KB   {2}" -f $name, ($size/1KB), $p.D) -ForegroundColor Green
        $ok++
    }
    catch {
        Write-Host ("  FAIL  {0,-30} {1}" -f $name, $_.Exception.Message) -ForegroundColor Yellow
        $fail += [pscustomobject]@{ File = $name; Url = $p.U; Part = $p.D }
    }
}

Write-Host ""
Write-Host ("=" * 62)
Write-Host ("Downloaded {0}   Already present {1}   Failed {2}" -f $ok, $skip, $fail.Count)

if ($fail.Count -gt 0) {
    Write-Host ""
    Write-Host "These need manual download - vendor sites change their URLs often:" -ForegroundColor Yellow
    $fail | ForEach-Object { Write-Host ("  {0,-30} {1}" -f $_.File, $_.Url) }
    $fail | Export-Csv -Path 'failed_downloads.csv' -NoTypeInformation
    Write-Host ""
    Write-Host "Written to failed_downloads.csv" -ForegroundColor Yellow
}
Write-Host ""
