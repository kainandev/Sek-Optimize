from config import *
from app.app import App


class Network(App):
    """Ferramentas de rede e diagnostico de conectividade."""

    def __init__(self):
        super().__init__()

    def flush_dns(self):
        self.run_command("Limpando DNS", COMMANDS["flush_dns"])

    def reset_network(self):
        self.run_command("Resetando configuracoes de rede", COMMANDS["reset_network"])

    def reset_winsock(self):
        self.run_command("Resetando Winsock", COMMANDS["reset_winsock"])

    def run_ipconfig(self):
        self.run_command("IPConfig", COMMANDS["run_ipconfig"])

    def ping_google(self):
        self.run_command("Ping Google", COMMANDS["ping_google"])

    def run_tracert(self):
        self.run_command("Traceroute Google", COMMANDS["run_tracert"])

    def run_nslookup(self):
        self.run_command("NSLookup Google", COMMANDS["run_nslookup"])

    def show_active_connections(self):
        self.run_command("Conexoes ativas (ESTABLISHED)", COMMANDS["show_active_connections"])

    def renew_ip(self):
        self.log_warn("A conexao de rede sera interrompida brevemente.")
        self.run_command("Renovando IP (release + renew)", COMMANDS["renew_ip"])

    def show_open_ports(self):
        self.run_command("Portas em escuta (LISTENING)", COMMANDS["show_open_ports"])

    def list_services_running(self):
        self.run_command("Servicos em execucao", COMMANDS["list_services_running"])

    def run_netstat(self):
        self.run_command("Netstat", "netstat -ano")

    def run_arp(self):
        self.run_command("Tabela ARP", "arp -a")

    def run_route(self):
        self.run_command("Tabela de Rotas", "route print")