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

# Importacoes opcionais Windows-only (nao quebra em outros SO)
try:
    import pythoncom
except ImportError:
    pythoncom = None

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
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
# Todos os comandos shell em um so lugar para facil manutencao.
# Funcoes que sao puramente Python nao aparecem aqui.
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

    # --- Arquivos ---
    "clean_prefetch": (
        r'del /q /f /s C:\Windows\Prefetch\*.*'
    ),
    "clean_windows_update": (
        r'net stop wuauserv'
        r' & del /q /f /s C:\Windows\SoftwareDistribution\Download\*.*'
        r' & net start wuauserv'
    ),

    # --- Sistema ---
    "disable_fast_startup": (
        r'reg add "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Power"'
        r' /v HiberbootEnabled /t REG_DWORD /d 0 /f'
    ),
    "kill_background_tasks": (
        r'taskkill /f /im OneDrive.exe & taskkill /f /im Teams.exe'
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
        r' & del /q /f /s C:\Windows\System32\spool\PRINTERS\*.*'
        r' & net start spooler'
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
}


# ============================================================
# ACTIONS
# Define cada acao, seu grupo, descricao e se e perigosa.
# "handler" aponta para o metodo do App ou para uma chave de COMMANDS.
# ============================================================
ACTIONS = {
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
        "description": "Desativa SysMain e outros servicos de alto uso de disco/memoria.",
        "tab": "Otimizacao",
        "danger": True,
        "handler": "disable_services",
    },
    5: {
        "label": "Limpar Arquivos Temporarios",
        "description": "Remove arquivos temporarios do usuario e do Windows.",
        "tab": "Arquivos",
        "danger": False,
        "handler": "clean_temp",
    },
    6: {
        "label": "Limpar Prefetch",
        "description": "Remove arquivos de pre-carregamento antigos do Windows.",
        "tab": "Arquivos",
        "danger": False,
        "handler": "clean_prefetch",
    },
    7: {
        "label": "Limpar Cache do Windows Update",
        "description": "Remove arquivos de atualizacoes antigas (pode ocupar varios GB).",
        "tab": "Arquivos",
        "danger": True,
        "handler": "clean_windows_update",
    },
    8: {
        "label": "Desativar Inicializacao Rapida",
        "description": "Desativa o Fast Startup para evitar problemas de boot e drivers.",
        "tab": "Sistema",
        "danger": True,
        "handler": "disable_fast_startup",
    },
    9: {
        "label": "Otimizacao Completa",
        "description": (
            "Executa um conjunto completo de otimizacoes seguras:\n"
            "- Transparencia\n- Game Mode\n- Plano de Energia\n"
            "- Efeitos Visuais\n- Servicos Pesados\n- Limpeza de Temporarios"
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
    14: {
        "label": "Encerrar Tarefas em Segundo Plano",
        "description": "Finaliza processos comuns que consomem recursos desnecessariamente.",
        "tab": "Sistema",
        "danger": True,
        "handler": "kill_background_tasks",
    },
    15: {
        "label": "Verificar Sistema (SFC)",
        "description": "Verifica e corrige arquivos corrompidos do Windows.",
        "tab": "Manutencao",
        "danger": False,
        "handler": "run_sfc",
    },
    16: {
        "label": "Reparar Windows (DISM)",
        "description": "Repara a imagem do Windows usada pelo sistema de atualizacao.",
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
    18: {
        "label": "IPConfig",
        "description": "Mostra configuracoes de rede (ipconfig /all).",
        "tab": "Diagnostico",
        "danger": False,
        "handler": "run_ipconfig",
    },
    19: {
        "label": "Executar MAS",
        "description": "Executa Microsoft Activation Scripts (janela externa).",
        "tab": "Ativacao",
        "danger": True,
        "handler": "run_massgrave",
    },
    20: {
        "label": "Ping Google",
        "description": "Testa conectividade com google.com.",
        "tab": "Diagnostico",
        "danger": False,
        "handler": "ping_google",
    },
    21: {
        "label": "Traceroute",
        "description": "Rastreia rota ate google.com.",
        "tab": "Diagnostico",
        "danger": False,
        "handler": "run_tracert",
    },
    22: {
        "label": "NSLookup",
        "description": "Consulta DNS do Google.",
        "tab": "Diagnostico",
        "danger": False,
        "handler": "run_nslookup",
    },
    23: {
        "label": "Saude do Disco (SMART)",
        "description": "Verifica o status SMART do disco.",
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
        "description": "Exibe uso, espaco livre e ocupacao do disco C:.",
        "tab": "Sistema",
        "danger": False,
        "handler": "disk_usage_report",
    },
    26: {
        "label": "Verificar Superficie do Disco",
        "description": "Verifica erros e setores defeituosos (pode exigir reinicio).",
        "tab": "Manutencao",
        "danger": True,
        "handler": "check_disk_surface",
    },
    27: {
        "label": "Reiniciar Spooler",
        "description": "Reinicia o servico de impressao e limpa filas travadas.",
        "tab": "Manutencao",
        "danger": True,
        "handler": "restart_print_spooler",
    },
    28: {
        "label": "Relatorio do Sistema",
        "description": "Coleta informacoes completas de hardware em formato de arvore.",
        "tab": "Sistema",
        "danger": False,
        "handler": "run_system_report",
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
    "cls"
]

# Arquivo de persistencia dos grupos de macro
GROUPS_FILE = "groups.json"

# ============================================================
# GRUPOS PADRAO (embutidos no codigo, nao dependem de JSON)
# Para adicionar um novo grupo padrao basta inserir uma entrada aqui.
# ============================================================
DEFAULT_GROUPS = {
    "Otimizacao Rapida": {
        "builtin": True,
        "actions": [0, 1, 2, 3],
    },
    "Limpeza Completa": {
        "builtin": True,
        "actions": [5, 6, 7],
    },
    "Manutencao Basica": {
        "builtin": True,
        "actions": [15, 16, 11],
    },
    "Diagnostico de Rede": {
        "builtin": True,
        "actions": [18, 20, 21, 22],
    },
    "Otimizacao Completa": {
        "builtin": True,
        "actions": [0, 1, 2, 3, 4, 5, 6, 11],
    },
}