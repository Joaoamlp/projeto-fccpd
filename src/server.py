"""
Servidor do Chat Distribuído RH <-> TI.
Gerencia conexões, turnos e mensagens entre dois departamentos (RH e TI)

Protocolo simples (linhas UTF-8 terminadas em '\n'):

- Mensagens servidor -> cliente:
    ROLE|<DEPT>|<START>
    TURN
    MSG|<SEQ>|<FROM>|<TEXT>
    INFO|<TEXT>
    SHUTDOWN

- Mensagens cliente -> servidor:
    MSG|<TEXT>
    QUIT
"""

# Importando bibliotecas
import socket
import threading
from typing import Dict, List, Tuple, Optional

# Variáveis de Ambiente
HOST = "127.0.0.1"
PORT = 8080
ENC = "utf-8"


class ClientInfo:
    """Informações de um cliente conectado."""

    def __init__(self, sock: socket.socket, addr: Tuple[str, int], dept: str) -> None:
        """
        Inicializa as informações do cliente.

        Args:
            sock (socket.socket): Socket do cliente.
            addr (Tuple[str, int]): Endereço do cliente. ex: ("127.0.0.1", 12345)
            dept (str): Nome do departamento ("RH" ou "TI").
        """
        self.sock = sock
        self.addr = addr
        self.dept = dept
        self.active = True


class ChatServer:
    """Servidor que gerencia turnos, histórico e comunicação entre dois clientes."""

    def __init__(self, host: str = HOST, port: int = PORT) -> None:
        """
        Inicializa o servido com host e porta.

        Args:
            host (str): Endereço para bind do servidor.
            port (int): Porta para bind do servidor.
        """
        self.host = host
        self.port = port
        self.server_sock: Optional[socket.socket] = None

        #Armazena clientes conectados
        self.clients: Dict[str, ClientInfo] = {}
        self.clients_lock = threading.Lock()

        #Histórico da conversa (seq, from_dep, texto)
        self.history: List[Tuple[int, str, str]] = []
        self.history_lock = threading.Lock()

        #Sequência global de mensagens
        self.seq = 0
        self.seq_lock = threading.Lock()

        #Quem tem o turno atual
        self.turn_dept: Optional[str] = None

        #Flag que sinaliza o término do servidor
        self.shutdown_event = threading.Event()

    def start(self) -> None:
        """
        Inicia o servidor e gerencia o ciclo de vida do chat.

        Aceita dois clientes, atribui papéis e controla a troca de mensagens.

        Raises:
            OSError: Se houver falha ao criar, bindar ou escutar no socket.
        """
        # Configurando o socket do servidor
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_sock.bind((self.host, self.port))
        self.server_sock.listen(2)
        print(f">> [SERVIDOR] Ouvindo em {self.host}:{self.port}")

        # Aceitando conexões até ter dois clientes
        while len(self.clients) < 2:
            sock, addr = self.server_sock.accept()

            # Criando e atribuindo cliente ao departamento
            with self.clients_lock:
                dept = "RH" if "RH" not in self.clients else "TI"
                info = ClientInfo(sock, addr, dept)
                self.clients[dept] = info
                print(f">> [SERVIDOR] {dept} conectado de {addr}")

                # Iniciando thread para o cliente
                t = threading.Thread(target=self._handle_client, args=(info,), daemon=True)
                t.start()

        # Definindo quem começa, se não definido
        if self.turn_dept is None:
            self.turn_dept = "RH"
        
        # Enviando roles e sinal inicial 
        self._send_roles_and_start()

        # Aguarda condição de shutdown (quando ambos inativos)
        self.shutdown_event.wait()
        self._finish()

    def _send_roles_and_start(self) -> None:
        """Envia ROLE e sinal inicial de TURN para o cliente inicial."""

        # enviando ROLE|<DEPT>|<START> e INFO|Bem-vindo ao chat <DEPT>. Aguarde seu turno.
        for dept, info in list(self.clients.items()):
            start_flag = "1" if dept == self.turn_dept else "0"
            self._send_raw(info.sock, f"ROLE|{dept}|{start_flag}\n")
            self._send_raw(info.sock, f"INFO|Bem-vindo ao chat {dept}. Aguarde seu turno.\n")
        #Dá o primeiro TURN pra quem vai começar
        starter = self.clients.get(self.turn_dept)
        if starter:
            self._send_raw(starter.sock, "TURN\n")

    def _handle_client(self, info: ClientInfo) -> None:
        """
        Loop receptor para cada cliente.

        Recebe linhas do socket e interpreta comandos MSG|<text> e QUIT.
        Notifica o outro cliente quando um desconecta.
                        
        Args:
            info (ClientInfo): Informações do cliente conectado.

        Raises:
            Exception: Caso o servidor não reconheça a mensagem / Caso ele não consiga marcar como inativo.
        """
        sock = info.sock
        f = sock.makefile("r", encoding=ENC, newline="\n")  #Leitura linha a linha
        try:
            for raw in f:
                line = raw.rstrip("\n")
                if not line:
                    continue
                if line.startswith("MSG|"):             #Mensagem normal
                    _, text = line.split("|", 1)
                    self._handle_msg_from_client(info.dept, text)
                elif line == "QUIT":                    #Cliente saiu explicitamente
                    self._handle_quit(info.dept)
                    break
                else:                                   #Mensagem inválida
                    print(f">> [SERVIDOR] Mensagem não reconhecida de {info.dept}: {line}")
        except Exception as e:
            print(f">> [SERVIDOR] Erro no cliente {info.dept}: {e}")
        finally:
            # marca inativo e notifica o outro (se houver)
            with self.clients_lock:
                info.active = False
                try:
                    info.sock.close()
                except Exception:
                    pass
            print(f">> [SERVIDOR] Conexão {info.dept} encerrada.")
            # notifica o outro se ainda estiver ativo, dando TURN para que continue
            other = "TI" if info.dept == "RH" else "RH"
            with self.clients_lock:
                if other in self.clients and self.clients[other].active:
                    self._send_raw(self.clients[other].sock, f"INFO|{info.dept} desconectou. Você pode continuar.\n")
                    self._send_raw(self.clients[other].sock, "TURN\n")
            #Se ambos saíram, aciona o SHUTDOWN
            if all(not c.active for c in self.clients.values()):
                self.shutdown_event.set()

    def _handle_msg_from_client(self, dept_from: str, text: str) -> None:
        """
        Registra a mensagem no histórico, encaminha ao outro e alterna o turno.

        Args:
            dept_from (str): Departamento remetente ("RH" ou "TI").
            text (str): Texto da mensagem.
        """
        #Incrementa contador global de mensagem
        with self.seq_lock:
            self.seq += 1
            seq = self.seq
        #Salva no histórico
        with self.history_lock:
            self.history.append((seq, dept_from, text))
        print(f">> [SERVIDOR] Msg recebida #{seq} de {dept_from}: {text!r}")

        other = "TI" if dept_from == "RH" else "RH"
        with self.clients_lock:
            if other in self.clients and self.clients[other].active:
                # envia apenas para o destinatário (não ecoa)
                self._send_raw(self.clients[other].sock, f"MSG|{seq}|{dept_from}|{text}\n")
                # define turno para o outro e envia TURN
                self.turn_dept = other
                self._send_raw(self.clients[other].sock, "TURN\n")
            else:
                # destinatário offline -> informa remetente e devolve TURN para que continue
                if dept_from in self.clients and self.clients[dept_from].active:
                    self._send_raw(self.clients[dept_from].sock, f"INFO|{other} offline. Sua mensagem foi registrada.\n")
                    # devolve TURN ao mesmo remetente para que ele possa continuar
                    self.turn_dept = dept_from
                    self._send_raw(self.clients[dept_from].sock, "TURN\n")

        # se a mensagem foi 'sair', marca o remetente inativo
        if text.strip().lower() == "sair":
            with self.clients_lock:
                if dept_from in self.clients:
                    self.clients[dept_from].active = False
            # se ambos inativos -> sinaliza fim
            if all(not c.active for c in self.clients.values()):
                self.shutdown_event.set()

    def _handle_quit(self, dept: str) -> None:
        """
        Lida com QUIT explícito do cliente.

        Args:
            dept (str): Departamento que enviou QUIT.
        """
        print(f">> [SERVIDOR] {dept} solicitou QUIT.")
        #Adiciona "sair" ao histórico
        with self.seq_lock:
            self.seq += 1
            seq = self.seq
        with self.history_lock:
            self.history.append((seq, dept, "sair"))
        #Marca cliente como inativo
        with self.clients_lock:
            if dept in self.clients:
                self.clients[dept].active = False
        #Informa ao outro cliente, se ainda estiver ativo
        other = "TI" if dept == "RH" else "RH"
        with self.clients_lock:
            if other in self.clients and self.clients[other].active:
                self._send_raw(self.clients[other].sock, f"INFO|{dept} saiu. Você ainda pode enviar mensagens.\n")
                self._send_raw(self.clients[other].sock, "TURN\n")
        if all(not c.active for c in self.clients.values()):
            self.shutdown_event.set()

    def _send_raw(self, sock: socket.socket, text: str) -> None:
        """
        Envia textos bruto para o cliente.

        Args:
            sock (socket.socket): Socket destino.
            text (str): Texto a enviar (deve incluir newline quando apropriado).

        Raise:
            Exception: Caso tenha falha no envio do socket.
        """
        try:
            sock.sendall(text.encode(ENC))
        except Exception as e:
            print(f">> [SERVIDOR] Erro enviando para cliente: {e}")

    def _finish(self) -> None:
        """
        Finaliza o servidor e encerra conexões.

        Imprime o histórico completo da conversa, envia 'SHUTDOWN' 
        aos clientes restantes e fecha todos os sockets.
        
        Raises:
            Exception: caso não consigo enviar mensagem de shutdown / Nem fechar o socket do (cliente / servidor).
        """
        #Mostra o histórico do chat ordenado
        print("\n>> [SERVIDOR] CHAT FINALIZADO! Conversa completa (ordenada):")
        for seq, frm, txt in sorted(self.history, key=lambda x: x[0]):
            print(f"#{seq:03d} [{frm}] {txt}")
        #Informa que vai encerrar clientes e sockets
        print("\n>> [SERVIDOR] Enviando SHUTDOWN para clientes restantes e fechando sockets.")
        with self.clients_lock:
            for info in self.clients.values():
                try:
                    if info.active:
                        #Notifica o cliente para desconectar
                        self._send_raw(info.sock, "SHUTDOWN\n")
                except Exception:
                    pass
                try:
                    #Fecha o socket do cliente
                    info.sock.close()
                except Exception:
                    pass
        #Fecha o socket para o servidor
        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass
        print(">> [SERVIDOR] Finalizado.")


def servidor_main(start_with: Optional[str] = None) -> None:
    """Função externa para iniciar o servidor.

    Args:
        start_with (Optional[str]): Opcionalmente "RH" ou "TI" para definir quem começa.
    """
    server = ChatServer()
    if start_with in ("RH", "TI"):
        server.turn_dept = start_with
    server.start()


if __name__ == "__main__":
    servidor_main()
