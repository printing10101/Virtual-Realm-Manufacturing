' VBScript: Trigger UAC elevation for netsh winsock reset
' Shows explanation first, then triggers UAC prompt

Option Explicit

Dim result, shell, fso, logFile, logPath

' Step 1: Show explanation message box
result = MsgBox( _
    "WinSock network stack is corrupted (WinError 10038)." & vbCrLf & vbCrLf & _
    "This blocks all network access including pip/conda downloads." & vbCrLf & _
    "torch cannot be installed until WinSock is fixed." & vbCrLf & vbCrLf & _
    "Next: A UAC (User Account Control) prompt will appear." & vbCrLf & _
    "Please click YES to allow 'netsh winsock reset' with admin rights." & vbCrLf & vbCrLf & _
    "After reset, you MUST restart your computer for it to take effect." & vbCrLf & vbCrLf & _
    "Click OK to continue, or Cancel to abort.", _
    vbOKCancel + vbExclamation, _
    "WinSock Repair - Admin Required" _
)

If result = vbCancel Then
    WScript.Echo "Operation cancelled by user."
    WScript.Quit(1)
End If

' Step 2: Trigger UAC elevation
Set shell = CreateObject("Shell.Application")
Set fso = CreateObject("Scripting.FileSystemObject")

logPath = "C:\Users\Lenovo\Desktop\winsock_reset_result.txt"

' Use cmd.exe to run netsh and capture output
shell.ShellExecute "cmd.exe", _
    "/c ""netsh winsock reset > """ & logPath & """ 2>&1 && echo SUCCESS >> """ & logPath & """ || echo FAILED >> """ & logPath & """ """, _
    "", "runas", 1

WScript.Echo "UAC prompt triggered. If you clicked YES, check:" & vbCrLf & logPath
WScript.Echo "If the UAC prompt did not appear, please right-click winsock_reset_admin.bat and select 'Run as administrator'."
