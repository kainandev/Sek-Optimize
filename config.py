import subprocess
import threading
import queue
import json
import os
import platform
import sys
import psutil
import getpass
import socket
import time
from datetime import datetime

# Importacoes opcionais Windows-only
try:
    import pythoncom
except ImportError:
    pythoncom = None

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
from collections import defaultdict

from util.system_details import *

VERSION_SOFTWARE = "0.2.0"

APP_ASCII = [
"           .:===++++++===:.           ",
"        .-=++==-::..::-=+++:-.        ",
"     ..=++=:...        ...::=+=:      ",
"    .-++=..          ..:-===++++=.    ",
"   .=+=...         .-++++++++++++=..  ",
"  .=+=..         .-+++++++++++++++=.  ",
"  -+=..         .-+++++++++++++++++-. ",
" .=+-.          :-:.......:==+++++=:. ",
" .++-...--                  .++=..%%: ",
" .++.:%%%..                 ::...=%%:.",
" .:#%%%%%%*-......:=+-          .*%%..",
"  +%%%%%%%%%%%%%%%%%*.          .%%+. ",
"  .#%%%%%%%%%%%%%%%*.          .%%#.  ",
"  ..#%%%%%%%%%%%%*:.         .:#%#..  ",
"    .*%%%%%##*=:.          ..*%%*..   ",
"      :#%#--..          ..-#%%#:.     ",
"        :*:%%%#+::::::+#%%%%*..       ",
"           .-##%%%%%%%%%#-...         ",
"                       ..             ",
"                                      "
]


# ============================================================
# COMMANDS
# Todos os comandos shell em um unico lugar.
# Para adicionar um novo comando shell, insira uma entrada aqui.
# Consulte COMMANDS.md para instrucoes detalhadas.
# ============================================================
COMMANDS = {

    # --- Otimizacao ---
    "disable_transparency": (
        r'reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"'
        r' /v EnableTransparency /t REG_DWORD /d 0 /f'
    ),
    "disable_gamemode": (
        r'reg add "HKCU\Software\Microsoft\GameBar" /v AutoGameModeEnabled /t REG_DWORD /d 0 /f'
        r' & reg add "HKCU\System\GameConfigStore" /v GameDVR_Enabled /t REG_DWORD /d 0 /f'
    ),
    "power_plan": (
        "powercfg -setactive SCHEME_MIN"
    ),
    "visual_effects": (
        r'reg add "HKCU\Control Panel\Desktop" /v DragFullWindows /t REG_SZ /d 0 /f'
        r' & reg add "HKCU\Control Panel\Desktop" /v MenuShowDelay /t REG_SZ /d 0 /f'
        r' & reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"'
        r' /v VisualFXSetting /t REG_DWORD /d 2 /f'
    ),
    "disable_services": (
        r'sc stop SysMain & sc config SysMain start= disabled'
    ),
    "restart_explorer": (
        "taskkill /f /im explorer.exe & start explorer.exe"
    ),
    "disable_hibernation": (
        "powercfg /h off"
    ),
    "disable_search_indexing": (
        r'sc stop WSearch & sc config WSearch start= disabled'
    ),

    # --- Limpeza ---
    "clean_prefetch": (
        r'del /q /f /s C:\Windows\Prefetch\*.*'
    ),
    "clean_windows_update": (
        r'net stop wuauserv'
        r' & del /q /f /s C:\Windows\SoftwareDistribution\Download\*.*'
        r' & net start wuauserv'
    ),
    "clean_recycle_bin": (
        r'powershell -NoProfile -Command "Clear-RecycleBin -Force -ErrorAction SilentlyContinue"'
    ),
    "clean_event_logs": (
        r'wevtutil cl System & wevtutil cl Application & wevtutil cl Security'
        r' & wevtutil cl Setup & wevtutil cl "Windows PowerShell"'
    ),
    "clean_thumbnail_cache": (
        r'taskkill /f /im explorer.exe 2>nul'
        r' & del /f /q "%LocalAppData%\Microsoft\Windows\Explorer\thumbcache_*.db" 2>nul'
        r' & start explorer.exe'
    ),
    "clean_edge_cache": (
        r'taskkill /f /im msedge.exe 2>nul'
        r' & rd /s /q "%LocalAppData%\Microsoft\Edge\User Data\Default\Cache" 2>nul'
        r' & rd /s /q "%LocalAppData%\Microsoft\Edge\User Data\Default\Code Cache" 2>nul'
        r' & echo Cache do Edge removido.'
    ),
    "clean_chrome_cache": (
        r'taskkill /f /im chrome.exe 2>nul'
        r' & rd /s /q "%LocalAppData%\Google\Chrome\User Data\Default\Cache" 2>nul'
        r' & rd /s /q "%LocalAppData%\Google\Chrome\User Data\Default\Code Cache" 2>nul'
        r' & echo Cache do Chrome removido.'
    ),
    "clean_wer": (
        r'rd /s /q "%LocalAppData%\Microsoft\Windows\WER" 2>nul'
        r' & rd /s /q "C:\ProgramData\Microsoft\Windows\WER\ReportQueue" 2>nul'
        r' & rd /s /q "C:\ProgramData\Microsoft\Windows\WER\ReportArchive" 2>nul'
        r' & echo Relatorios de erros do Windows removidos.'
    ),
    "clean_restore_points": (
        r'vssadmin delete shadows /for=C: /oldest /quiet'
    ),

    # --- Sistema ---
    "disable_fast_startup": (
        r'reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power"'
        r' /v HiberbootEnabled /t REG_DWORD /d 0 /f'
    ),
    "kill_background_tasks": (
        r'taskkill /f /im OneDrive.exe 2>nul & taskkill /f /im Teams.exe 2>nul'
    ),
    "check_disk_health": (
        "wmic diskdrive get model,status,interfacetype,mediatype"
    ),
    "disk_info": (
        "wmic diskdrive get model,serialnumber,size,mediatype"
    ),
    "check_disk_surface": (
        "chkdsk C: /f /r"
    ),
    "restart_print_spooler": (
        r'net stop spooler'
        r' & del /q /f /s C:\Windows\System32\spool\PRINTERS\*.* 2>nul'
        r' & net start spooler'
    ),
    "list_installed_programs": (
        r'powershell -NoProfile -Command "'
        r'Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*,'
        r'HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*'
        r' | Select-Object DisplayName,DisplayVersion'
        r' | Where-Object {$_.DisplayName -ne $null}'
        r' | Sort-Object DisplayName'
        r' | Format-Table -AutoSize"'
    ),
    "check_drivers": (
        "driverquery /fo list"
    ),
    "check_updates_hotfix": (
        r'powershell -NoProfile -Command "'
        r'Get-HotFix | Sort-Object InstalledOn -Descending'
        r' | Select-Object -First 20'
        r' | Format-Table HotFixID,Description,InstalledOn -AutoSize"'
    ),

    # --- Rede ---
    "flush_dns": (
        "ipconfig /flushdns"
    ),
    "reset_network": (
        r'netsh int ip reset & netsh winsock reset & ipconfig /flushdns'
    ),
    "reset_winsock": (
        "netsh winsock reset"
    ),
    "run_ipconfig": (
        "ipconfig /all"
    ),
    "ping_google": (
        "ping google.com"
    ),
    "run_tracert": (
        "tracert google.com"
    ),
    "run_nslookup": (
        "nslookup google.com"
    ),
    "show_active_connections": (
        r'netstat -ano | findstr ESTABLISHED'
    ),
    "renew_ip": (
        "ipconfig /release & ipconfig /renew"
    ),
    "show_open_ports": (
        r'netstat -ano | findstr LISTENING'
    ),

    # --- Manutencao ---
    "run_sfc": (
        "sfc /scannow"
    ),
    "run_dism": (
        "dism /online /cleanup-image /restorehealth"
    ),
    "run_chkdsk": (
        "chkdsk C: /f /r"
    ),
    "defrag_hdd": (
        "defrag C: /U /V"
    ),
    "trim_ssd": (
        "defrag C: /L"
    ),
    "reset_gpo": (
        r'gpupdate /force'
    ),
    "repair_store": (
        "wsreset.exe"
    ),
    "verify_dotnet": (
        r'powershell -NoProfile -Command "'
        r'Get-ChildItem \"HKLM:\SOFTWARE\Microsoft\NET Framework Setup\NDP\" -Recurse'
        r' | Get-ItemProperty -Name Version,Release -ErrorAction SilentlyContinue'
        r' | Where-Object { $_.PSChildName -Match \"^(?!S)\p{L}\" }'
        r' | Select-Object PSChildName, Version'
        r' | Format-Table -AutoSize"'
    ),

    # --- Privacidade ---
    "disable_telemetry": (
        r'reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection"'
        r' /v AllowTelemetry /t REG_DWORD /d 0 /f'
        r' & reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\DataCollection"'
        r' /v AllowTelemetry /t REG_DWORD /d 0 /f'
        r' & sc stop DiagTrack & sc config DiagTrack start= disabled'
    ),
    "disable_cortana": (
        r'reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Search"'
        r' /v AllowCortana /t REG_DWORD /d 0 /f'
        r' & reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Search"'
        r' /v CortanaEnabled /t REG_DWORD /d 0 /f'
    ),
    "disable_xbox_dvr": (
        r'reg add "HKCU\System\GameConfigStore" /v GameDVR_Enabled /t REG_DWORD /d 0 /f'
        r' & reg add "HKLM\SOFTWARE\Policies\Microsoft\Windows\GameDVR"'
        r' /v AllowGameDVR /t REG_DWORD /d 0 /f'
    ),
    "disable_remote_desktop": (
        r'reg add "HKLM\SYSTEM\CurrentControlSet\Control\Terminal Server"'
        r' /v fDenyTSConnections /t REG_DWORD /d 1 /f'
        r' & netsh advfirewall firewall set rule group="remote desktop" new enable=No'
    ),
    "list_startup_programs": (
        r'reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run"'
        r' & reg query "HKLM\Software\Microsoft\Windows\CurrentVersion\Run"'
        r' & reg query "HKLM\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run" 2>nul'
    ),
    "export_users": (
        "net user"
    ),

    # --- Monitor ---
    "list_services_running": (
        r'powershell -NoProfile -Command "'
        r'Get-Service | Where-Object {$_.Status -eq \"Running\"}'
        r' | Sort-Object DisplayName'
        r' | Format-Table Name,DisplayName,Status -AutoSize"'
    ),

    # --- Seguranca ---
    "defender_quick_scan": (
        r'"C:\Program Files\Windows Defender\MpCmdRun.exe" -Scan -ScanType 1'
    ),
}


# ============================================================
# ACTIONS
# Define cada acao que aparece na interface.
# "handler" aponta para chave em COMMANDS (shell) ou metodo Python.
# Consulte COMMANDS.md para instrucoes de como adicionar novas acoes.
# ============================================================
ACTIONS = {

    # --- Otimizacao ---
    0: {
        "label": "Desativar Transparencia",
        "description": "Remove efeitos de transparencia do Windows, reduzindo uso de GPU e memoria.",
        "tab": "Otimizacao",
        "danger": False,
        "handler": "disable_transparency",
    },
    1: {
        "label": "Desativar Game Mode",
        "description": "Desativa Game Mode, Game Bar e gravacoes em segundo plano.",
        "tab": "Otimizacao",
        "danger": False,
        "handler": "disable_gamemode",
    },
    2: {
        "label": "Plano de Energia (Max. Desempenho)",
        "description": "Define o plano de energia para maximo desempenho.",
        "tab": "Otimizacao",
        "danger": False,
        "handler": "power_plan",
    },
    3: {
        "label": "Efeitos Visuais (Desempenho)",
        "description": "Reduz animacoes e efeitos visuais para deixar o sistema mais rapido.",
        "tab": "Otimizacao",
        "danger": False,
        "handler": "visual_effects",
    },
    4: {
        "label": "Desativar Servicos Pesados",
        "description": "Desativa SysMain e outros servicos de alto uso de disco e memoria.",
        "tab": "Otimizacao",
        "danger": True,
        "handler": "disable_services",
    },
    9: {
        "label": "Otimizacao Completa",
        "description": (
            "Executa conjunto completo de otimizacoes:\n"
            "- Transparencia, Game Mode, Plano de Energia\n"
            "- Efeitos Visuais, Servicos Pesados, Temp, DNS"
        ),
        "tab": "Otimizacao",
        "danger": True,
        "handler": "optimize_all",
    },
    10: {
        "label": "Reiniciar Explorer",
        "description": "Reinicia a interface grafica do Windows sem reiniciar o PC.",
        "tab": "Otimizacao",
        "danger": True,
        "handler": "restart_explorer",
    },
    58: {
        "label": "Desativar Hibernacao",
        "description": "Desativa a hibernacao e remove o hiberfil.sys, liberando GBs no disco.",
        "tab": "Otimizacao",
        "danger": True,
        "handler": "disable_hibernation",
    },
    59: {
        "label": "Desativar Indexacao de Busca",
        "description": "Para o Windows Search de indexar arquivos em segundo plano, reduzindo uso de disco.",
        "tab": "Otimizacao",
        "danger": True,
        "handler": "disable_search_indexing",
    },

    # --- Limpeza ---
    5: {
        "label": "Limpar Arquivos Temporarios",
        "description": "Remove arquivos temporarios do usuario e da pasta Windows Temp.",
        "tab": "Limpeza",
        "danger": False,
        "handler": "clean_temp",
    },
    6: {
        "label": "Limpar Prefetch",
        "description": "Remove arquivos de pre-carregamento antigos do Windows.",
        "tab": "Limpeza",
        "danger": False,
        "handler": "clean_prefetch",
    },
    7: {
        "label": "Limpar Cache do Windows Update",
        "description": "Para o servico, remove cache de atualizacoes antigas e reinicia.",
        "tab": "Limpeza",
        "danger": True,
        "handler": "clean_windows_update",
    },
    42: {
        "label": "Limpar Lixeira",
        "description": "Esvazia a lixeira de todas as unidades do sistema.",
        "tab": "Limpeza",
        "danger": False,
        "handler": "clean_recycle_bin",
    },
    43: {
        "label": "Limpar Event Logs",
        "description": "Apaga logs de eventos (System, Application, Security). Util para liberar espaco e privacidade.",
        "tab": "Limpeza",
        "danger": True,
        "handler": "clean_event_logs",
    },
    44: {
        "label": "Limpar Cache de Miniaturas",
        "description": "Remove o banco de dados de miniaturas do Explorer (thumbcache). Reinicia o Explorer.",
        "tab": "Limpeza",
        "danger": False,
        "handler": "clean_thumbnail_cache",
    },
    45: {
        "label": "Limpar Cache do Edge",
        "description": "Fecha o Microsoft Edge e remove o cache de navegacao.",
        "tab": "Limpeza",
        "danger": False,
        "handler": "clean_edge_cache",
    },
    46: {
        "label": "Limpar Cache do Chrome",
        "description": "Fecha o Google Chrome e remove o cache de navegacao.",
        "tab": "Limpeza",
        "danger": False,
        "handler": "clean_chrome_cache",
    },
    47: {
        "label": "Limpar WER (Relatorios de Erro)",
        "description": "Remove dumps e relatorios de travamento armazenados pelo Windows Error Reporting.",
        "tab": "Limpeza",
        "danger": False,
        "handler": "clean_wer",
    },
    48: {
        "label": "Remover Ponto de Restauracao Antigo",
        "description": "Remove o ponto de restauracao mais antigo do C:, liberando espaco (vssadmin).",
        "tab": "Limpeza",
        "danger": True,
        "handler": "clean_restore_points",
    },

    # --- Sistema ---
    8: {
        "label": "Desativar Inicializacao Rapida",
        "description": "Desativa o Fast Startup para evitar problemas de boot e drivers.",
        "tab": "Sistema",
        "danger": True,
        "handler": "disable_fast_startup",
    },
    14: {
        "label": "Encerrar Tarefas em Segundo Plano",
        "description": "Finaliza OneDrive e Teams, que consomem recursos desnecessariamente.",
        "tab": "Sistema",
        "danger": True,
        "handler": "kill_background_tasks",
    },
    23: {
        "label": "Saude do Disco (SMART)",
        "description": "Verifica o status SMART do disco via WMIC.",
        "tab": "Sistema",
        "danger": False,
        "handler": "check_disk_health",
    },
    24: {
        "label": "Informacoes do Disco",
        "description": "Mostra modelo, tipo e tamanho do disco.",
        "tab": "Sistema",
        "danger": False,
        "handler": "disk_info",
    },
    25: {
        "label": "Uso do Disco",
        "description": "Exibe uso, espaco livre e ocupacao do disco C: via Python.",
        "tab": "Sistema",
        "danger": False,
        "handler": "disk_usage_report",
    },
    28: {
        "label": "Relatorio do Sistema",
        "description": "Coleta informacoes completas de hardware (CPU, RAM, GPU, Discos) via WMI.",
        "tab": "Sistema",
        "danger": False,
        "handler": "run_system_report",
    },
    49: {
        "label": "Listar Programas Instalados",
        "description": "Exibe todos os programas instalados com versao via registro do Windows.",
        "tab": "Sistema",
        "danger": False,
        "handler": "list_installed_programs",
    },
    50: {
        "label": "Verificar Drivers",
        "description": "Lista todos os drivers instalados no sistema.",
        "tab": "Sistema",
        "danger": False,
        "handler": "check_drivers",
    },
    51: {
        "label": "Snapshot do Sistema",
        "description": "Captura instantaneo de CPU, RAM, disco, rede e uptime no momento atual.",
        "tab": "Sistema",
        "danger": False,
        "handler": "system_snapshot",
    },
    52: {
        "label": "Atualizacoes Recentes (HotFix)",
        "description": "Lista as 20 atualizacoes de seguranca instaladas mais recentes.",
        "tab": "Sistema",
        "danger": False,
        "handler": "check_updates_hotfix",
    },

    # --- Rede ---
    11: {
        "label": "Limpar DNS",
        "description": "Limpa o cache DNS para corrigir falhas de acesso a internet.",
        "tab": "Rede",
        "danger": False,
        "handler": "flush_dns",
    },
    12: {
        "label": "Resetar Rede (Completo)",
        "description": "Reseta TCP/IP, Winsock e DNS. Pode exigir reinicializacao.",
        "tab": "Rede",
        "danger": True,
        "handler": "reset_network",
    },
    13: {
        "label": "Reset Winsock",
        "description": "Reseta apenas o Winsock, util para erros de conexao.",
        "tab": "Rede",
        "danger": True,
        "handler": "reset_winsock",
    },
    18: {
        "label": "IPConfig",
        "description": "Mostra configuracoes de rede (ipconfig /all).",
        "tab": "Rede",
        "danger": False,
        "handler": "run_ipconfig",
    },
    20: {
        "label": "Ping Google",
        "description": "Testa conectividade com google.com.",
        "tab": "Rede",
        "danger": False,
        "handler": "ping_google",
    },
    21: {
        "label": "Traceroute",
        "description": "Rastreia rota ate google.com.",
        "tab": "Rede",
        "danger": False,
        "handler": "run_tracert",
    },
    22: {
        "label": "NSLookup",
        "description": "Consulta DNS do Google.",
        "tab": "Rede",
        "danger": False,
        "handler": "run_nslookup",
    },
    60: {
        "label": "Testar Velocidade DNS",
        "description": "Compara tempo de resposta entre DNS do Google (8.8.8.8), Cloudflare (1.1.1.1) e OpenDNS.",
        "tab": "Rede",
        "danger": False,
        "handler": "test_dns_speed",
    },
    61: {
        "label": "Conexoes Ativas (ESTABLISHED)",
        "description": "Filtra o netstat mostrando apenas conexoes ativas no momento.",
        "tab": "Rede",
        "danger": False,
        "handler": "show_active_connections",
    },
    62: {
        "label": "Exportar Configuracao de Rede",
        "description": "Salva ipconfig /all em arquivo .txt com data/hora no diretorio atual.",
        "tab": "Rede",
        "danger": False,
        "handler": "export_network_config",
    },
    63: {
        "label": "Renovar IP (Release + Renew)",
        "description": "Libera e renova o endereco IP da maquina.",
        "tab": "Rede",
        "danger": True,
        "handler": "renew_ip",
    },
    64: {
        "label": "Portas em Escuta (LISTENING)",
        "description": "Filtra o netstat mostrando apenas portas abertas aguardando conexao.",
        "tab": "Rede",
        "danger": False,
        "handler": "show_open_ports",
    },

    # --- Manutencao ---
    15: {
        "label": "Verificar Sistema (SFC)",
        "description": "Verifica e corrige arquivos corrompidos do Windows (pode demorar varios minutos).",
        "tab": "Manutencao",
        "danger": False,
        "handler": "run_sfc",
    },
    16: {
        "label": "Reparar Windows (DISM)",
        "description": "Repara a imagem do Windows usada pelo sistema de atualizacao (pode demorar).",
        "tab": "Manutencao",
        "danger": False,
        "handler": "run_dism",
    },
    17: {
        "label": "Verificar Disco (CHKDSK)",
        "description": "Agenda verificacao completa do disco no proximo boot.",
        "tab": "Manutencao",
        "danger": True,
        "handler": "run_chkdsk",
    },
    26: {
        "label": "Verificar Superficie do Disco",
        "description": "Verifica erros fisicos e setores defeituosos (pode exigir reinicio).",
        "tab": "Manutencao",
        "danger": True,
        "handler": "check_disk_surface",
    },
    27: {
        "label": "Reiniciar Spooler de Impressao",
        "description": "Reinicia o servico de impressao e limpa filas de impressao travadas.",
        "tab": "Manutencao",
        "danger": True,
        "handler": "restart_print_spooler",
    },
    53: {
        "label": "Desfragmentar Disco (HDD)",
        "description": "Desfragmenta o disco C:. Usar apenas em HD mecanico, NAO em SSD.",
        "tab": "Manutencao",
        "danger": True,
        "handler": "defrag_hdd",
    },
    54: {
        "label": "Otimizar SSD (TRIM)",
        "description": "Executa TRIM no SSD C: para manter performance. Nao use em HDD.",
        "tab": "Manutencao",
        "danger": False,
        "handler": "trim_ssd",
    },
    55: {
        "label": "Resetar Politicas de Grupo (GPO)",
        "description": "Forca atualizacao das politicas de grupo (gpupdate /force).",
        "tab": "Manutencao",
        "danger": True,
        "handler": "reset_gpo",
    },
    56: {
        "label": "Reparar Microsoft Store",
        "description": "Executa wsreset.exe para corrigir problemas na Microsoft Store.",
        "tab": "Manutencao",
        "danger": False,
        "handler": "repair_store",
    },
    57: {
        "label": "Verificar .NET Framework",
        "description": "Lista as versoes do .NET Framework instaladas no sistema.",
        "tab": "Manutencao",
        "danger": False,
        "handler": "verify_dotnet",
    },

    # --- Monitor (nova aba) ---
    29: {
        "label": "Snapshot CPU / RAM / Disco",
        "description": "Exibe uso instantaneo de CPU, memoria, disco e rede via psutil.",
        "tab": "Monitor",
        "danger": False,
        "handler": "system_snapshot",
    },
    30: {
        "label": "Top 10 Processos (CPU)",
        "description": "Lista os 10 processos que mais consomem CPU no momento.",
        "tab": "Monitor",
        "danger": False,
        "handler": "top_processes_cpu",
    },
    31: {
        "label": "Top 10 Processos (RAM)",
        "description": "Lista os 10 processos que mais consomem memoria RAM no momento.",
        "tab": "Monitor",
        "danger": False,
        "handler": "top_processes_ram",
    },
    32: {
        "label": "Servicos em Execucao",
        "description": "Lista todos os servicos do Windows que estao ativos no momento.",
        "tab": "Monitor",
        "danger": False,
        "handler": "list_services_running",
    },
    33: {
        "label": "Informacoes de Bateria",
        "description": "Exibe nivel, status e capacidade da bateria (notebooks).",
        "tab": "Monitor",
        "danger": False,
        "handler": "battery_info",
    },

    # --- Privacidade (nova aba) ---
    34: {
        "label": "Desativar Telemetria",
        "description": "Bloqueia coleta de dados de diagnostico e uso enviados a Microsoft.",
        "tab": "Privacidade",
        "danger": True,
        "handler": "disable_telemetry",
    },
    35: {
        "label": "Desativar Cortana",
        "description": "Desativa o assistente virtual Cortana via politica de grupo.",
        "tab": "Privacidade",
        "danger": False,
        "handler": "disable_cortana",
    },
    36: {
        "label": "Desativar Xbox Game DVR",
        "description": "Remove o overlay de gravacao do Xbox, reduzindo uso de GPU e latencia.",
        "tab": "Privacidade",
        "danger": False,
        "handler": "disable_xbox_dvr",
    },
    37: {
        "label": "Desativar Remote Desktop (RDP)",
        "description": "Desativa o Remote Desktop para reduzir superficie de ataque remoto.",
        "tab": "Privacidade",
        "danger": True,
        "handler": "disable_remote_desktop",
    },
    38: {
        "label": "Listar Programas na Inicializacao",
        "description": "Exibe tudo que e carregado automaticamente ao ligar o PC (registro Run).",
        "tab": "Privacidade",
        "danger": False,
        "handler": "list_startup_programs",
    },
    39: {
        "label": "Listar Usuarios do Sistema",
        "description": "Lista todas as contas de usuario locais via net user.",
        "tab": "Privacidade",
        "danger": False,
        "handler": "export_users",
    },

    # --- Seguranca (nova aba) ---
    40: {
        "label": "Windows Defender - Scan Rapido",
        "description": "Executa um scan rapido via MpCmdRun.exe. Requer Windows Defender ativo.",
        "tab": "Seguranca",
        "danger": False,
        "handler": "defender_quick_scan",
    },
    41: {
        "label": "Exibir Arquivo HOSTS",
        "description": "Mostra o conteudo do arquivo hosts do Windows (C:\\Windows\\System32\\drivers\\etc\\hosts).",
        "tab": "Seguranca",
        "danger": False,
        "handler": "show_hosts_file",
    },

    # --- Diagnostico ---
    19: {
        "label": "Executar MAS",
        "description": "Executa Microsoft Activation Scripts em janela externa.",
        "tab": "Ativacao",
        "danger": True,
        "handler": "run_massgrave",
    },
}


AUTOCOMPLETE_COMMANDS = [
    "ipconfig",
    "ping",
    "tracert",
    "nslookup",
    "netstat",
    "arp",
    "route",
    "systeminfo",
    "tasklist",
    "driverquery",
    "sfc /scannow",
    "dism /online /cleanup-image /restorehealth",
    "gpupdate /force",
    "cls",
]

# Arquivo de persistencia dos grupos customizados pelo usuario
GROUPS_FILE = "groups.json"

# ============================================================
# GRUPOS PADRAO (embutidos, nao dependem de JSON)
# Para adicionar um grupo padrao, insira uma entrada aqui.
# ============================================================
DEFAULT_GROUPS = {
    "Otimizacao Rapida": {
        "builtin": True,
        "actions": [0, 1, 2, 3],
    },
    "Limpeza Basica": {
        "builtin": True,
        "actions": [5, 6, 42, 47],
    },
    "Limpeza Completa": {
        "builtin": True,
        "actions": [5, 6, 7, 42, 43, 44, 47],
    },
    "Manutencao Basica": {
        "builtin": True,
        "actions": [15, 16, 11],
    },
    "Diagnostico de Rede": {
        "builtin": True,
        "actions": [18, 20, 21, 22, 60],
    },
    "Privacidade Basica": {
        "builtin": True,
        "actions": [34, 35, 36],
    },
    "Otimizacao Completa": {
        "builtin": True,
        "actions": [0, 1, 2, 3, 4, 5, 6, 11, 58],
    },
    "Suporte Tecnico": {
        "builtin": True,
        "actions": [51, 28, 25, 23, 50, 52],
    },
}