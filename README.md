# 💬 Chat Corporativo RH–TI

Protótipo de **sistema de chat distribuído** entre dois departamentos de uma empresa (**Recursos Humanos** e **Tecnologia da Informação**), desenvolvido em **Python**.  

A solução adota **arquitetura cliente-servidor** sobre **sockets TCP**, utilizando **threads** para lidar com concorrência no envio/recebimento de mensagens e mecanismos de **sincronização** (locks e eventos) para garantir:  
- alternância de turnos,  
- consistência no histórico,  
- finalização limpa.  

Este projeto foi desenvolvido como parte de um estudo acadêmico no **CESAR (Centro de Estudos e Sistemas Avançados do Recife)**.

---

## ✨ Funcionalidades

- **Arquitetura Cliente-Servidor**  
  - Servidor central controla conexões, turnos e histórico.  
  - Simplicidade no roteamento: servidor decide para quem enviar.  

- **Comunicação por Turnos**  
  - Usuário escolhe quem começa (RH ou TI).  
  - Alternância automática de turnos após cada mensagem.  

- **Mensagens Robusta**  
  - O remetente não vê eco da própria mensagem.  
  - Se o destinatário estiver offline, o servidor informa e devolve o turno.  

- **Concorrência**  
  - Threads no servidor para cada conexão.  
  - Thread dedicada no cliente para receber mensagens continuamente.  
  - Uso de `threading.Lock` para proteger histórico e sequência.  
  - Uso de `threading.Event` para controle de turnos.  

- **Finalização Limpa**  
  - Comando `sair` encerra o cliente.  
  - Servidor finaliza a conversa quando ambos encerram, exibindo o histórico completo.  

---

## 🏗️ Arquitetura

O sistema contém três componentes principais:

- **`server.py`** → servidor central, controla clientes, turnos e histórico.  
- **`client.py`** → cliente genérico (RH ou TI), com threads para envio e recebimento.  
- **`run_all.py`** → orquestrador que inicia o servidor (em processo separado) e os dois clientes (em threads).  

### 🔄 Protocolo de Mensagens

- **Cliente → Servidor**
  - `MSG <texto>` → envio de mensagem  
  - `QUIT` → encerra cliente  

- **Servidor → Cliente**
  - `ROLE <DEPT>|<START>` → papel do cliente (RH/TI) e se inicia  
  - `TURN` → vez de enviar mensagem  
  - `MSG <seq>|<FROM>|<texto>` → entrega de mensagem ao destinatário  
  - `INFO <texto>` → mensagens informativas  
  - `SHUTDOWN` → solicitação de encerramento  

---

## 🚀 Como Executar

Clone o repositório e rode o script de orquestração na pasta src:

```bash
python run_all.py
O programa pedirá para escolher qual departamento inicia a conversa.

🖥️ Exemplo de Uso
text
Copy code
>> [MAIN] Escolha quem inicia:
1 - RH
2 - TI
Escolha: 1

>> [SERVIDOR] Ouvindo em 127.0.0.1:8080
>> [CLIENTE] RH conectado
>> [CLIENTE] TI conectado

[RH] Digite sua mensagem (ou 'sair'): Olá TI
>> [SERVIDOR] Msg #1 de RH: "Olá TI"

[TI -> RH] #1 Olá TI
[TI] Digite sua mensagem (ou 'sair'): Oi RH
>> [SERVIDOR] Msg #2 de TI: "Oi RH"

[RH -> TI] #2 Oi RH
[RH] Digite sua mensagem (ou 'sair'): sair
...
>> [SERVIDOR] CHAT FINALIZADO! Histórico:
#001 [RH] Olá TI
#002 [TI] Oi RH
#003 [RH] sair
#004 [TI] sair
```
## ⚠️ Limitações
- Ponto único de falha: se o servidor cair, toda a comunicação é perdida.

- Escalabilidade limitada: atualmente suporta apenas dois clientes (RH e TI).

- Protocolo simples: baseado em linhas; pode falhar com mensagens que contenham quebras de linha.

## 🔮 Próximos Passos
- Persistência do histórico em arquivo ou banco de dados.

- Implementação de testes automatizados (unitários e de integração).

- Versão assíncrona com asyncio para comparar desempenho.

## 👥 Integrantes

- Arthur Capistrano

- Érico Chen

- Gheyson Melo

- João Antônio

- Thiago Manguinho

- Gabriel Tabosa

## 📍 CESAR — Projeto Acadêmico


