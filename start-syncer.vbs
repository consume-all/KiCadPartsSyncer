' Launch the companion hidden at login (no console window)
Dim bat
bat = "C:\dev\work\KiCadPartsSyncer\start-companion.bat"   ' <-- ABSOLUTE PATH
CreateObject("Wscript.Shell").Run """" & bat & """", 0, False