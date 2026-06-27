# Teamcenter × N8N — Spec Técnica e PRD
## Gatilhos de Workflow como Disparo Externo para Automação com N8N

**Versão:** 1.0  
**Data:** 2026-06-27  
**Status:** Rascunho  
**Repositório:** andrefixplm/smartchm2pdf  

---

## Índice

1. [Visão Geral](#1-visão-geral)
2. [Contexto e Problema](#2-contexto-e-problema)
3. [Mecanismos de Disparo no Teamcenter](#3-mecanismos-de-disparo-no-teamcenter)
4. [Arquiteturas de Integração](#4-arquiteturas-de-integração-disponíveis)
5. [Licenciamento do N8N](#5-licenciamento-do-n8n)
6. [PRD — Requisitos do Produto](#6-prd--requisitos-do-produto)
7. [Roadmap de Implementação](#7-roadmap-de-implementação)
8. [Critérios de Aceite](#8-critérios-de-aceite)
9. [Riscos e Mitigações](#9-riscos-e-mitigações)
10. [Referências](#10-referências)

---

## 1. Visão Geral

Este documento especifica a arquitetura e os requisitos para uma solução de integração entre os **workflows do Teamcenter (Siemens PLM)** e a plataforma de automação **N8N**. O objetivo é criar um padrão reutilizável — um **framework de integração TC→N8N** — que possa ser implantado em múltiplos clientes com custo mínimo de licenciamento e máxima flexibilidade de automação.

A solução permite que qualquer etapa de um workflow do Teamcenter dispare um ou mais workflows do N8N, habilitando:
- Geração automática de documentos (ex.: CHM → PDF)
- Notificações para Slack, Teams, e-mail, ERP
- Sincronização com SAP, Oracle, Jira, etc.
- Aprovações via chatbot ou formulário externo
- Qualquer outra automação suportada pelos 400+ conectores do N8N

---

## 2. Contexto e Problema

### 2.1 Por que integrar Teamcenter com N8N?

O Teamcenter gerencia o ciclo de vida do produto (PLM), mas frequentemente precisa acionar sistemas externos quando uma etapa de workflow é concluída. As opções nativas do Teamcenter são:

| Mecanismo nativo | Limitação |
|---|---|
| EPM-notify (e-mail interno) | Só envia e-mail, não aciona lógica |
| Dispatcher Framework | Requer licença adicional; configuração complexa |
| Custom ITK handlers (C/C++) | Requer compilação, build C, ambiente de desenvolvimento |
| SOAP/REST SOA | Direcional: externo → TC; TC não empurra dados nativamente |

O N8N resolve esse gap com uma plataforma de automação visual, self-hosted, low-code, com suporte a webhooks, que pode receber disparos e executar qualquer lógica de integração subsequente.

### 2.2 Público-alvo da solução

- Administradores de Teamcenter que precisam de automações sem desenvolver ITK em C
- Consultores PLM que precisam de uma solução replicável em múltiplos clientes
- Empresas que já usam Teamcenter e querem reduzir custo de integrações customizadas

---

## 3. Mecanismos de Disparo no Teamcenter

### 3.1 Conceito: Actions e Handlers em Workflows EPM

Todo workflow no Teamcenter é modelado no **EPM (Enterprise Process Modeling)**. Cada tarefa (task) possui **Actions** (ações) às quais se podem vincular **Handlers** (manipuladores — código que executa quando a ação é ativada).

#### Ações disponíveis por tarefa (flags de trigger)

| Action Flag | Momento de disparo |
|---|---|
| `start` | Quando a tarefa se torna ativa no workflow |
| `perform` | Quando o usuário clica em "Perform Task" |
| `complete` | Quando a tarefa é concluída com sucesso |
| `approve` | Quando uma Review Task é aprovada |
| `reject` | Quando uma Review Task é rejeitada |
| `skip` | Quando a tarefa é ignorada/pulada |
| `abort` | Quando o workflow é abortado |
| `suspend` | Quando o workflow é suspenso |
| `resume` | Quando o workflow é retomado após suspensão |
| `undo` | Quando a tarefa é desfeita (demoted) |

**Implicação prática:** qualquer um desses eventos pode ser usado como gatilho para chamar o N8N. O mais comum será `complete` e `approve`.

---

### 3.2 Tipos de Tasks (Tarefas)

| Tipo de Task | Uso típico | Melhor para trigger? |
|---|---|---|
| **Do Task** | Ação genérica de usuário | Sim — mais flexível |
| **Review Task** | Aprovação/rejeição formal | Sim — approve/reject |
| **Acknowledge Task** | Confirmação de ciência | Sim |
| **Route Task** | Circulação de documentos | Sim |
| **Condition Task** | Desvio condicional de rota | Sim — lógica de branching |
| **Validate Task** | Verificação com erros esperados | Sim |
| **Status Task** | Atribuição de release status | Sim |
| **Or Task** | Continua quando qualquer predecessor termina | Sim |
| **Custom Task** | Site-específico | Sim — mais controle |

---

### 3.3 Handlers de Ação Nativos (OOTB Action Handlers)

Handlers disponíveis out-of-the-box para referência e contexto:

| Handler | Função |
|---|---|
| `EPM-notify` | Envia e-mail interno Teamcenter |
| `EPM-notify-report` | Envia e-mail externo (SMTP) com relatório |
| `EPM-create-status` | Cria e aplica um status de release |
| `EPM-create-sub-process` | Cria um sub-workflow |
| `EPM-auto-assign` | Atribui responsáveis automaticamente |
| `EPM-attach-related-objects` | Vincula objetos ao workflow |
| `EPM-adhoc-signoffs` | Gerencia aprovações ad hoc |
| `EPM-change-ownership` | Altera proprietário do objeto |
| `EPM-demote` | Retrocede o workflow |
| `EPM-set-status` | Define status nos targets |

---

### 3.4 Handlers para Execução Externa (Mecanismos de Trigger)

Estes são os handlers críticos que permitem chamar sistemas externos:

#### 3.4.1 `EPM-run-external-command`

Executa um comando OS diretamente no servidor do Teamcenter.

**Como usar:**
```
Handler Name: EPM-run-external-command
Arguments:
  -program  <caminho absoluto do executável ou script>
  -args     <argumentos passados ao script>
```

**Exemplo de configuração no Workflow Designer:**
```
-program /opt/tc_integration/scripts/trigger_n8n.sh
-args TASK_NAME=$(task.name) OBJECT_UID=$(target.uid) USER=$(user.name)
```

O script `trigger_n8n.sh` faz um `curl` para o webhook do N8N:
```bash
#!/bin/bash
curl -X POST https://n8n.empresa.com/webhook/tc-trigger \
  -H "Content-Type: application/json" \
  -d "{\"task\": \"$1\", \"uid\": \"$2\", \"user\": \"$3\"}"
```

**Limitações:**
- O script roda como usuário do processo Teamcenter (permissões limitadas)
- Sem retorno de dados ao workflow (fire-and-forget)
- Requer que o servidor TC tenha acesso de rede ao N8N

#### 3.4.2 `EPM-invoke-system-action`

Executa um executável ITK (binário compilado) no contexto do servidor Teamcenter.

**Como usar:**
```
Handler Name: EPM-invoke-system-action
Arguments:
  -action   <nome da system action registrada>
  -program  <executável ITK>
```

**Diferença do EPM-run-external-command:** O binário executado tem acesso à sessão Teamcenter e pode ler/escrever objetos PLM antes de chamar o N8N, enriquecendo o payload.

#### 3.4.3 Custom ITK Action Handler (C/C++)

O método mais robusto. Desenvolve-se um handler em C usando as APIs do Teamcenter:

```c
// Exemplo simplificado de handler ITK com libcurl
#include <epm/epm.h>
#include <tc/tc.h>
#include <curl/curl.h>

int USER_custom_n8n_trigger(EPM_action_message_t msg) {
    tag_t task_tag = msg.task;
    char *task_name;
    EPM_ask_name(task_tag, &task_name);
    
    // Monta payload JSON
    char payload[2048];
    sprintf(payload, 
        "{\"task\":\"%s\",\"workflow\":\"%s\",\"timestamp\":\"%s\"}",
        task_name, workflow_name, timestamp);
    
    // Chama N8N via HTTP
    CURL *curl = curl_easy_init();
    curl_easy_setopt(curl, CURLOPT_URL, "http://n8n:5678/webhook/tc-trigger");
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload);
    curl_easy_perform(curl);
    curl_easy_cleanup(curl);
    
    return ITK_ok;
}
```

**Registro do handler via BMIDE:**
- Definir `Action Handler` no BMIDE apontando para a função
- Compilar com o toolkit TC (gcc + TC includes + libcurl)
- Implantar o `.so` (Linux) ou `.dll` (Windows) no servidor

**Vantagens:**
- Acesso completo ao modelo de dados PLM
- Pode incluir atributos de itens, revisões, datasets, relações
- Pode ser síncrono (aguarda resposta N8N) ou assíncrono
- Mais confiável e auditável

---

### 3.5 Subscrição de Eventos via BMIDE

Além de handlers de workflow, o BMIDE permite registrar **Post-Action Handlers** para eventos de objetos, que disparam independentemente de estar em um workflow:

| Evento de Objeto | Descrição |
|---|---|
| `SAVE` | Após salvar um objeto |
| `CREATE` | Após criar um objeto |
| `MODIFY` | Após modificar um atributo |
| `DELETE` | Após deletar um objeto |
| `STATUS_CHANGE` | Quando o release status muda |
| `CHECKOUT` / `CHECKIN` | Check-out/check-in de datasets |

Esses eventos podem acionar o N8N mesmo sem um workflow ativo, cobrindo cenários como:
- "Quando um Item Revision for liberado (Released), gerar PDF automaticamente"
- "Quando um Dataset for criado, notificar equipe de qualidade"

---

### 3.6 SOA (Service-Oriented Architecture) — Direção Inversa

O SOA do Teamcenter permite que **sistemas externos chamem o Teamcenter**:

```
HTTP POST / SOAP  →  TC Web Tier  →  Business Logic Server
```

**WorkflowService.createInstance()** — Inicia um workflow programaticamente:
```java
ContextData contextData = new ContextData();
contextData.setAttachmentUIDs(new String[]{"UID_DO_OBJETO"});
contextData.setAttachmentTypes(new int[]{EPM_target_attachment});
contextData.setProcessTemplate("Nome_do_Template");

InstanceInfo result = wfService.createInstance(
    true, null, "Nome do Processo", null, "Descrição", contextData);
```

**Uso no contexto TC→N8N:** O SOA é útil na **direção inversa**: o N8N pode chamar o TC SOA para criar um workflow, consultar status, ou atualizar atributos — criando loops de automação bidirecionais.

---

## 4. Arquiteturas de Integração Disponíveis

### Arquitetura A: Script-Based (Recomendada para início)

```
Teamcenter Workflow
       │
   [Task Complete]
       │
EPM-run-external-command
       │
   trigger_n8n.sh (Python/Bash no servidor TC)
       │
   HTTP POST (curl/requests)
       │
   N8N Webhook Trigger
       │
   N8N Workflow executa
   ├── Geração de PDF
   ├── Notificação Slack/Teams
   ├── Update SAP/ERP
   └── Qualquer outro nó N8N
```

**Prós:** Simples de implementar, sem compilação C, reaproveitável  
**Contras:** Sem acesso ao modelo PLM no momento do disparo, fire-and-forget

---

### Arquitetura B: Custom ITK Handler (Recomendada para produção)

```
Teamcenter Workflow
       │
   [Task Complete/Approve/Reject]
       │
Custom ITK Handler (.so/.dll)
   ├── Lê atributos do objeto (ITK API)
   ├── Lê attachments do workflow
   ├── Monta payload JSON rico
       │
   HTTP POST com libcurl
       │
   N8N Webhook Trigger
       │
   N8N Workflow executa com contexto completo
```

**Prós:** Payload completo com dados PLM, confiável, auditável  
**Contras:** Requer ambiente de build C/C++ com TC toolkit

---

### Arquitetura C: BMIDE Event + Bridge Service

```
Teamcenter Object Event (SAVE/STATUS_CHANGE)
       │
BMIDE Post-Action Handler
       │
   Escreve em fila/tabela (JMS, DB, arquivo)
       │
Bridge Service (Java/Python daemon)
   ├── Polling da fila/tabela
       │
   HTTP POST para N8N
       │
   N8N Workflow
```

**Prós:** Desacoplado, tolerante a falhas, auditável  
**Contras:** Mais componentes para manter, latência adicional

---

### Arquitetura D: Bidirecional Completa (SOA + Webhook)

```
TC Workflow  ─[trigger]→  N8N  ─[SOA call]→  TC (atualiza dados)
                           │
                     Outros sistemas
```

O N8N pode fechar o loop chamando o TC SOA para:
- Atualizar atributos do item
- Criar novos objetos/datasets
- Avançar/reprovar tasks de workflow programaticamente
- Iniciar novos workflows

---

## 5. Licenciamento do N8N

### 5.1 Modelo de Licença

O N8N utiliza a **Sustainable Use License** (licença de uso sustentável), um modelo **fair-code** — não é MIT/Apache/GPL, mas o código-fonte é disponível.

> "n8n is free to *use*, not free to *monetize*."

### 5.2 O que é permitido SEM custo de licença

| Caso de Uso | Permitido? |
|---|---|
| Self-hosting em servidor próprio | ✅ Sim |
| Uso interno de uma empresa | ✅ Sim |
| Consultor configura e implanta no ambiente do cliente | ✅ Sim |
| Consultor cria workflows para uso interno do cliente | ✅ Sim |
| Modificação do código-fonte para uso interno | ✅ Sim |
| Distribuição gratuita para uso interno de clientes | ✅ Sim |
| Múltiplos clientes (cada um usa internamente) | ✅ Sim |

### 5.3 O que REQUER licença comercial

| Caso de Uso | Permitido sem licença? |
|---|---|
| Hospedar N8N e cobrar clientes pelo acesso | ❌ Não |
| White-label: vender N8N como produto próprio | ❌ Não |
| SaaS onde usuários externos disparam workflows | ❌ Não |
| N8N como componente central de produto vendido | ❌ Não |

### 5.4 Conclusão para Consultores PLM

**Sim, você pode implantar o N8N em múltiplos clientes sem custo de licença**, desde que:
- Cada implantação seja para uso interno daquele cliente
- Você não cobre pelo acesso ao N8N em si (pode cobrar pelo serviço de configuração/consultoria)
- O cliente não revenda a automação como produto para terceiros

O modelo é ideal para consultores: a implantação é gratuita, o valor está no know-how de configuração e integração.

### 5.5 Edições Disponíveis

| Edição | Custo | Features extras |
|---|---|---|
| **Community (self-hosted)** | Gratuita | Básico, sem limites de workflows |
| **Starter** | ~$20/mês (cloud) | 5 usuários, auditoria |
| **Pro** | ~$50/mês (cloud) | Mais usuários, debug avançado |
| **Enterprise** | Negociado | SSO, LDAP, suporte, SLA |

Para implantações em clientes enterprise (Teamcenter geralmente é enterprise), recomendar **self-hosted Community** com possível upgrade para **Enterprise** se o cliente precisar de SSO/LDAP.

---

## 6. PRD — Requisitos do Produto

### 6.1 Nome do Produto

**SMARTTC2N8N** — Framework de integração Teamcenter-to-N8N para automação de processos PLM

### 6.2 Objetivo

Fornecer um conjunto reutilizável de componentes (scripts, handlers, templates N8N, documentação) que permita a qualquer consultor PLM implementar automações N8N disparadas por eventos de workflow do Teamcenter em menos de 2 dias de trabalho.

### 6.3 Personas

**P1 — Administrador de Teamcenter**
- Configura workflows no Workflow Designer
- Não programa C, mas sabe usar o Workflow Designer
- Quer vincular actions a automações sem código complexo

**P2 — Consultor PLM**
- Implementa soluções para múltiplos clientes
- Precisa de componentes reutilizáveis
- Quer minimizar tempo de configuração por cliente

**P3 — Usuário Final PLM**
- Executa tarefas no workflow
- Não precisa saber que o N8N existe
- Se beneficia das automações (recebe PDF, notificação, etc.)

### 6.4 Requisitos Funcionais

#### RF-01: Trigger via Script (Arquitetura A)

- [ ] Script Python/Bash que recebe argumentos do workflow TC
- [ ] Formata payload JSON com dados do contexto do workflow
- [ ] Faz HTTP POST autenticado para o webhook N8N
- [ ] Logging local para auditoria
- [ ] Retry automático em caso de falha de rede

#### RF-02: Custom ITK Handler (Arquitetura B)

- [ ] Handler C/C++ compilável com TC toolkit 12.x+
- [ ] Extrai dados de objeto (item, revision, dataset) via API ITK
- [ ] Extrai dados do workflow (task name, template, assignees)
- [ ] Monta payload JSON configurável
- [ ] Suporte a chamada síncrona (aguarda resposta) e assíncrona
- [ ] Configurável via preferências do Teamcenter (sem recompilação)

#### RF-03: Templates de Workflow N8N

- [ ] Template: "TC Workflow Complete → Gerar PDF"
- [ ] Template: "TC Workflow Approve → Notificar Slack"
- [ ] Template: "TC Status Change → Sync SAP"
- [ ] Template: "TC Workflow Reject → Criar Tarefa Jira"
- [ ] Template genérico: "TC Event → HTTP Request para qualquer sistema"

#### RF-04: Configuração Declarativa

- [ ] Arquivo de configuração YAML/JSON para mapear:
  - Workflow template → N8N webhook URL
  - Task name → ação a executar
  - Campos do objeto → campos do payload

#### RF-05: Monitoramento e Auditoria

- [ ] Log de todas as chamadas ao N8N (timestamp, status HTTP, payload)
- [ ] Dashboard N8N mostrando histórico de execuções
- [ ] Alertas para falhas de integração

#### RF-06: Segurança

- [ ] Autenticação no webhook N8N (Bearer token ou Basic Auth)
- [ ] HTTPS obrigatório para comunicação TC → N8N
- [ ] Opção de VPN/rede interna para instalações on-premise
- [ ] Não expor credenciais Teamcenter no payload N8N

### 6.5 Requisitos Não-Funcionais

| Requisito | Meta |
|---|---|
| Latência do disparo | < 3 segundos após conclusão da task |
| Disponibilidade | 99,5% (follow a disponibilidade do TC) |
| Retry em falha | Até 3 tentativas com backoff exponencial |
| Logs retidos | 90 dias |
| Compatibilidade TC | Teamcenter 12.x, 13.x, 14.x (AWC 5.x+) |
| Compatibilidade N8N | N8N >= 1.0 (Community ou Enterprise) |

---

## 7. Roadmap de Implementação

### Fase 1 — Prova de Conceito (2-4 semanas)

**Objetivo:** Validar a Arquitetura A (script-based) em ambiente de desenvolvimento

- [ ] Instalar N8N self-hosted (Docker)
- [ ] Criar primeiro workflow N8N com Webhook Trigger
- [ ] Configurar EPM-run-external-command em um workflow TC de teste
- [ ] Escrever script `trigger_n8n.py` mínimo (curl/requests)
- [ ] Testar disparo end-to-end
- [ ] Documentar setup do ambiente

**Entregáveis:**
- Script `trigger_n8n.py` funcional
- Workflow N8N de teste
- Workflow TC de teste configurado
- README de setup

---

### Fase 2 — Framework Reutilizável (4-6 semanas)

**Objetivo:** Transformar o PoC em componentes reutilizáveis

- [ ] Desenvolver `tc_n8n_bridge.py` (script parametrizável)
  - Suporte a múltiplos webhooks por workflow/task
  - Configuração via YAML
  - Logging estruturado
  - Retry com backoff
- [ ] Criar biblioteca de templates N8N (exportáveis como JSON)
- [ ] Documentação de instalação para admins TC
- [ ] Script de setup automático (instalação do bridge no servidor TC)

**Entregáveis:**
- Pacote `tc_n8n_bridge` (Python)
- 5 templates N8N prontos
- Guia de instalação

---

### Fase 3 — Custom ITK Handler (6-10 semanas)

**Objetivo:** Versão enterprise com handler C/C++ nativo

- [ ] Setup do ambiente de desenvolvimento ITK (TC toolkit + gcc + libcurl)
- [ ] Desenvolver `EPM_n8n_trigger_handler.c`
- [ ] Testes unitários e integração com TC dev
- [ ] Documentação de build e deploy
- [ ] Script de instalação do handler no TC production

**Entregáveis:**
- Código-fonte do handler C
- Makefile para compilação
- Binários pré-compilados (Linux x64 + Windows x64)
- Guia de deploy

---

### Fase 4 — Portal de Configuração (8-12 semanas)

**Objetivo:** Interface para admins configurarem triggers sem editar arquivos

- [ ] Web UI para mapear: workflow → webhook → payload
- [ ] Integração com TC SOA para listar workflows e templates disponíveis
- [ ] Interface para testar webhook antes de ativar
- [ ] Painel de monitoramento de execuções

---

## 8. Critérios de Aceite

### Cenário 1: Disparo básico
- **Dado** que um workflow TC tem EPM-run-external-command configurado na action `complete`
- **Quando** o usuário completa a task no Teamcenter
- **Então** o N8N deve receber o webhook em < 5 segundos com payload correto

### Cenário 2: Payload com dados PLM
- **Dado** que o handler customizado está instalado
- **Quando** uma Review Task é aprovada
- **Então** o payload N8N deve incluir: ID do item, revisão, nome do workflow, nome da task, usuário aprovador, data/hora

### Cenário 3: Resiliência
- **Dado** que o N8N está temporariamente indisponível
- **Quando** o TC tenta disparar o webhook
- **Então** o sistema deve fazer até 3 tentativas e logar o erro sem travar o workflow

### Cenário 4: Multi-cliente
- **Dado** que o framework está instalado em 2 clientes diferentes
- **Quando** cada cliente configura seu próprio mapeamento
- **Então** não deve haver conflito nem dependência entre as instâncias

---

## 9. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| TC server sem acesso de rede ao N8N | Alta | Alto | Usar proxy reverso ou VPN interna; documentar requisitos de rede |
| Versão TC incompatível com ITK handler | Média | Alto | Testar nas versões 12, 13, 14; scripts Python como fallback |
| N8N fora do ar trava workflow TC | Média | Alto | Fire-and-forget no script; workflow não aguarda resposta HTTP |
| Segurança: token N8N exposto em args | Alta | Alto | Armazenar token em env var ou arquivo protegido; nunca em args visíveis no Workflow Designer |
| Custo N8N para uso comercial | Baixa | Médio | Cada cliente usa internamente → gratuito; documentar o modelo |
| Performance: handler C segura GC do TC | Baixa | Alto | Usar chamadas HTTP assíncronas (non-blocking); timeout curto |

---

## 10. Referências

### Documentação Técnica Teamcenter
- [Teamcenter Workflow Handlers — Global PLM](https://globalplm.com/teamcenter-workflow-handlers/)
- [Workflow Designer Concept — Global PLM](https://globalplm.com/workflow-designer-teamcenter/)
- [PLM Handbook: Introduction to TC Workflows](https://plmhandbook.blogspot.com/2020/09/introduction-to-teamcenter-workflows.html)
- [TC SOA Guide — PLM Coach](https://plmcoach.com/teamcenter-soa-guide/)
- [SOA WorkflowService — TC Open Gate](https://teamcenter-open-gate.blogspot.com/2016/12/soa-serive-client-workflow-service-in.html)
- [EPM-invoke-system-action (Siemens Community)](https://community.sw.siemens.com/s/question/0D54O00006gNthrSAC/epminvokesystemaction-to-execute-a-batch-file)
- [EPM-run-external-command (Siemens Community)](https://community.sw.siemens.com/s/question/0D54O00007mdNRWSA2/does-anyone-have-experience-with-the-workflow-handler-epmrunexternalcommand)
- [Leveraging Action and Rule Handlers — LinkedIn](https://www.linkedin.com/pulse/leveraging-action-rule-handlers-teamcenters-enterprise-sxoic)

### Documentação N8N
- [N8N GitHub (fair-code)](https://github.com/n8n-io/n8n)
- [Sustainable Use License — N8N Docs](https://docs.n8n.io/privacy-and-security/sustainable-use-license)
- [N8N Licensing Explained — Scalevise](https://scalevise.com/resources/n8n-automation-license-commercial-use/)
- [N8N Licenses: Fair-code, Community, Enterprise — DigitalCube](https://digitalcube.ai/en/blog/n8n-licencias-fair-code-community-enterprise)

---

*Documento gerado como planejamento inicial. Deve ser revisado e refinado com base em testes de PoC e feedback dos clientes piloto.*
