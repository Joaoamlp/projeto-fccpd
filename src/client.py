"""Cliente do Chat Distribuído RH <-> TI.

O cliente interpreta sinais do servidor: ROLE, TURN, MSG, INFO, SHUTDOWN.
Quando recebe TURN, solicita input e envia MSG|<texto> ou QUIT.
"""

import time
import socket
import threading
from typing import Optional, NoReturn

HOST = "127.0.0.1"
PORT = 8080
ENC = "utf-8"


class ChatClient:
    """Cliente TCP que conversa com o ChatServer."""

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        """
        Args:
            host: Endereço do servidor.
            port: Porta do servidor.
        """
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.role: Optional[str] = None
        self.running = threading.Event()
        self.turn_event = threading.Event()
        self.receiver_thread: Optional[threading.Thread] = None

    def connect(self) -> None:
        """Conecta ao servidor e inicia a thread receptora."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.running.set()
        self.receiver_thread = threading.Thread(target=self._receiver_loop, daemon=True)
        self.receiver_thread.start()

    def _receiver_loop(self) -> None:
        """Recebe linhas do servidor e os interpreta.

        Sinais importantes:
            ROLE|<DEPT>|<START> -> define role e, se START == 1, seta turno.
            TURN -> seta turno (turn_event).
            MSG|seq|FROM|TEXT -> imprime mensagem recebida (somente destinatário).
            INFO|... -> imprime informação.
            SHUTDOWN -> encerra o cliente.
        """
        assert self.sock is not None
        f = self.sock.makefile("r", encoding=ENC, newline="\n")
        try:
            for raw in f:
                line = raw.rstrip("\n")
                if not line:
                    continue
                if line.startswith("ROLE|"):
                    _, role, start_flag = line.split("|")
                    self.role = role
                    if start_flag == "1":
                        self.turn_event.set()
                elif line == "TURN":
                    self.turn_event.set()
                elif line.startswith("MSG|"):
                    _, seq, frm, text = line.split("|", 3)
                    print(f"[{frm} -> {self.role}] #{seq} {text}")
                elif line.startswith("INFO|"):
                    _, text = line.split("|", 1)
                    print(f"[INFO] {text}")
                elif line == "SHUTDOWN":
                    print(">> [CLIENT] Servidor solicitou shutdown. Encerrando cliente.")
                    # sinaliza término e acorda qualquer wait no input
                    self.running.clear()
                    self.turn_event.set()
                    break
                else:
                    print(f"[CLIENT] Mensagem do servidor: {line}")
        except Exception as e:
            print(f">> [CLIENT] Erro no receptor: {e}")
        finally:
            # garante que qualquer wait seja liberado e running fique falso
            self.running.clear()
            self.turn_event.set()
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass

    def run_interactive(self) -> NoReturn:
        """Laço principal de envio: espera TURN e solicita input do usuário.

        O cliente não imprime sua própria mensagem localmente (requisito).
        """
        assert self.sock is not None
        try:
            while self.running.is_set():
                # espera pelo turno (com timeout curto para checar running)
                self.turn_event.wait(timeout=0.5)
                if not self.running.is_set():
                    break
                if not self.turn_event.is_set():
                    # volta a aguardar
                    continue
                # agora é o turno - solicita input (bloqueante)
                try:
                    time.sleep(0.5)
                    msg = input(f"\n[{self.role}] Digite sua mensagem (ou 'sair'): ").strip()
                except EOFError:
                    msg = "sair"
                if msg.lower() == "sair":
                    # envia mensagem de saída e QUIT
                    self._send_raw("MSG|sair\n")
                    self._send_raw("QUIT\n")
                    # não imprime localmente
                    break
                # envia mensagem normal
                self._send_raw(f"MSG|{msg}\n")
                # limpa o evento e aguarda próxima TURN do servidor
                self.turn_event.clear()
            print(f">> [CLIENT] {self.role} encerrando localmente.")
        finally:
            self.running.clear()
            try:
                if self.sock:
                    self.sock.close()
            except Exception:
                pass

    def _send_raw(self, text: str) -> None:
        """Envia texto ao servidor com tratamento de erro.

        Args:
            text: Texto a ser enviado (inclui '\n' quando aplicável).
        """
        try:
            if self.sock:
                self.sock.sendall(text.encode(ENC))
        except Exception as e:
            print(f">> [CLIENT] Erro ao enviar: {e}")
            self.running.clear()

    def close(self) -> None:
        """Força fechamento do cliente."""
        self.running.clear()
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass


def cliente(departamento: str, iniciar: bool) -> None:
    """Entrada compatível com run_all.py para iniciar cliente.

    Args:
        departamento: Nome do departamento (apenas informativo).
        iniciar: Parâmetro compatível com versão anterior; servidor decide quem começa.
    """
    client = ChatClient()
    client.connect()
    client.run_interactive()


if __name__ == "__main__":
    cliente("RH", True)
