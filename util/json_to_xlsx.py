import os
import json
import pandas as pd
from tkinter import Tk, filedialog

# =========================
# Seleciona a pasta
# =========================
Tk().withdraw()

PASTA_JSON = filedialog.askdirectory(
    title="Selecione a pasta onde estão os arquivos JSON"
)

if not PASTA_JSON:
    print("Nenhuma pasta selecionada.")
    exit()

# =========================
# Arquivo de saída
# =========================
ARQUIVO_SAIDA = os.path.join(PASTA_JSON, "inventario_maquinas.xlsx")

dados = []

# =========================
# Leitura dos JSONs
# =========================
for arquivo in os.listdir(PASTA_JSON):

    if arquivo.lower().endswith(".json"):

        caminho_arquivo = os.path.join(PASTA_JSON, arquivo)

        try:
            with open(caminho_arquivo, "r", encoding="utf-8") as f:
                j = json.load(f)

            # =========================
            # COMPONENTES
            # =========================

            drive = (
                j.get("storage", {})
                 .get("drives", [{}])
            )

            drive = drive[0] if drive else {}

            volume = (
                j.get("storage", {})
                 .get("volumes", [{}])
            )

            volume = volume[0] if volume else {}

            gpu = j.get("gpu", [{}])
            gpu = gpu[0] if gpu else {}

            rede = (
                j.get("network", {})
                 .get("adapters", [{}])
            )

            rede = rede[0] if rede else {}

            antivirus = j.get("antivirus", [{}])
            antivirus = antivirus[0] if antivirus else {}

            memoria_modulos = (
                j.get("memory", {})
                 .get("modules", [])
            )

            memoria_info = []

            for modulo in memoria_modulos:
                memoria_info.append(
                    f"{modulo.get('capacity_gb', 'N/A')}GB "
                    f"{modulo.get('type', '')} "
                    f"{modulo.get('speed_mhz', '')}MHz"
                )

            memoria_info = " | ".join(memoria_info)

            # =========================
            # PROGRAMAS INSTALADOS
            # =========================

            programas = j.get("installed_programs", [])

            nomes_programas = []

            for p in programas:
                nome = p.get("name")

                if nome:
                    nomes_programas.append(nome)

            programas_texto = " | ".join(nomes_programas)

            # =========================
            # LINHA DO INVENTÁRIO
            # =========================

            linha = {

                # GERAL
                "Arquivo": arquivo,
                "Hostname": j.get("system", {}).get("hostname"),
                "Usuario": j.get("system", {}).get("username"),
                "Sistema_Operacional": j.get("system", {}).get("os_edition"),
                "Versao_Windows": j.get("system", {}).get("os_version"),
                "Build_Windows": j.get("system", {}).get("os_build"),
                "Arquitetura": j.get("system", {}).get("os_architecture"),
                "Serial_Windows": j.get("system", {}).get("os_serial"),
                "Tipo_Licenca": j.get("system", {}).get("os_license_type"),
                "Data_Instalacao_Windows": j.get("system", {}).get("os_install_date"),
                "Boot_Mode": j.get("system", {}).get("boot_mode"),
                "Boot_Time": j.get("system", {}).get("boot_time"),
                "Uptime": j.get("system", {}).get("uptime"),
                "Qtd_Processos": j.get("system", {}).get("processes"),

                # CPU
                "CPU_Modelo": j.get("cpu", {}).get("model"),
                "CPU_Fabricante": j.get("cpu", {}).get("manufacturer"),
                "CPU_Nucleos_Fisicos": j.get("cpu", {}).get("physical_cores"),
                "CPU_Nucleos_Logicos": j.get("cpu", {}).get("logical_cores"),
                "CPU_Frequencia_Base": j.get("cpu", {}).get("frequency_base"),
                "CPU_Max_Clock_MHz": j.get("cpu", {}).get("max_clock_mhz"),
                "Virtualizacao": j.get("cpu", {}).get("virtualization"),

                # MEMÓRIA
                "RAM_Total_GB": j.get("memory", {}).get("total_gb"),
                "RAM_Usada_GB": j.get("memory", {}).get("used_gb"),
                "RAM_Disponivel_GB": j.get("memory", {}).get("available_gb"),
                "RAM_Uso_%": j.get("memory", {}).get("usage_pct"),
                "Slots_RAM": j.get("memory", {}).get("total_slots"),
                "RAM_Maxima_Suportada_GB": j.get("memory", {}).get("max_supported_gb"),
                "Modulos_RAM": memoria_info,

                # DISCO
                "Disco_Modelo": drive.get("model"),
                "Disco_Interface": drive.get("interface"),
                "Disco_Tipo": drive.get("media_type"),
                "Disco_Tamanho_GB": drive.get("size_gb"),
                "Disco_Serial": drive.get("serial_number"),
                "Disco_Firmware": drive.get("firmware"),

                # VOLUME
                "Particao": volume.get("mount_point"),
                "Filesystem": volume.get("filesystem"),
                "Espaco_Total_GB": volume.get("total_gb"),
                "Espaco_Usado_GB": volume.get("used_gb"),
                "Espaco_Livre_GB": volume.get("free_gb"),
                "Uso_Disco_%": volume.get("usage_pct"),

                # GPU
                "GPU": gpu.get("name"),
                "GPU_RAM_MB": gpu.get("adapter_ram_mb"),
                "GPU_Driver": gpu.get("driver_version"),
                "Resolucao": gpu.get("video_mode"),

                # REDE
                "Placa_Rede": rede.get("description"),
                "IP": (
                    rede.get("ip_addresses", [""])[0]
                    if rede.get("ip_addresses")
                    else ""
                ),
                "MAC": rede.get("mac_address"),
                "Gateway": (
                    rede.get("default_gateway", [""])[0]
                    if rede.get("default_gateway")
                    else ""
                ),
                "DHCP": rede.get("dhcp_enabled"),
                "Servidor_DHCP": rede.get("dhcp_server"),

                # BIOS
                "BIOS_Fabricante": j.get("bios", {}).get("vendor"),
                "BIOS_Versao": j.get("bios", {}).get("version"),
                "BIOS_Data": j.get("bios", {}).get("release_date"),

                # PLACA MÃE
                "PlacaMae_Fabricante": j.get("motherboard", {}).get("manufacturer"),
                "PlacaMae_Modelo": j.get("motherboard", {}).get("model"),
                "PlacaMae_Versao": j.get("motherboard", {}).get("version"),

                # ANTIVÍRUS
                "Antivirus": antivirus.get("name"),
                "Antivirus_Ativo": antivirus.get("enabled"),
                "Antivirus_Atualizado": antivirus.get("up_to_date"),

                # SOFTWARE
                "Python_Version": j.get("software", {}).get("python_version"),
                "App_Name": j.get("software", {}).get("app_name"),

                # PROGRAMAS
                "Programas_Instalados": programas_texto
            }

            dados.append(linha)

            print(f"[OK] {arquivo}")

        except Exception as e:
            print(f"[ERRO] {arquivo} -> {e}")

# =========================
# EXPORTA PARA EXCEL
# =========================

df = pd.DataFrame(dados)

with pd.ExcelWriter(ARQUIVO_SAIDA, engine="openpyxl") as writer:
    df.to_excel(writer, index=False, sheet_name="Inventario")

print("\n===================================")
print("INVENTÁRIO GERADO COM SUCESSO")
print(ARQUIVO_SAIDA)
print("===================================")