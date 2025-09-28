"""Script para iniciar servidor e clientes RH e TI.

O servidor roda em um Process (multiprocessing) e os clientes em threads
dentro deste processo principal, demonstrando tanto processos quanto threads.
"""

from __future__ import annotations

import multiprocessing
import threading
import time
from server import servidor_main
from client import cliente


def main() -> None:
    """Orquestra a inicialização do servidor e dos clientes."""
    print(">> [MAIN] Escolha quem irá iniciar a mensagem:")
    print("1 RH")
    print("2 TI")
    escolha = input("Escolha: ").strip()
    iniciar_rh = escolha == "1"

    start_with = "RH" if iniciar_rh else "TI"
    server_proc = multiprocessing.Process(target=servidor_main, args=(start_with,), daemon=False)
    server_proc.start()
    time.sleep(0.5)

    thread_rh = threading.Thread(target=cliente, args=("RH", iniciar_rh), daemon=False)
    thread_ti = threading.Thread(target=cliente, args=("TI", not iniciar_rh), daemon=False)

    thread_rh.start()
    thread_ti.start()

    thread_rh.join()
    thread_ti.join()

    if server_proc.is_alive():
        print(">> [MAIN] Esperando servidor encerrar...")
        server_proc.join(timeout=5)
        if server_proc.is_alive():
            print(">> [MAIN] Finalizando processo do servidor forçadamente.")
            server_proc.terminate()
    print(">> [MAIN] Todos os componentes encerrados. Fim.")


if __name__ == "__main__":
    main()
