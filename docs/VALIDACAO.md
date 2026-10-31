# Validação do MVP — 29/10/2026

Build executado: **IRIS AI Hub EAP 2026.3.0AI.154.0 / 154U**, Linux amd64. Uma Production, dois workflows, um Agent, cinco ferramentas, um modelo AutoML e coleção vetorial de 384 dimensões. Dados exclusivamente sintéticos.

## Resultados

- **35 testes aprovados** dentro do Embedded Python: contratos, guards, permissões, consentimento, FHIR R4, SQL/vector, AutoML, Java PEX, timeout real, Workflow Engine, TTL e segurança do seed.
- **12 casos de aceite do seed aprovados**, com OpenAI real: [relatório](demo-acceptance.json). Transferência recebeu 12 unidades; campanha concluiu processamento e liberou 15. Recebimento/liberação não foram registrados como utilização.
- Cinco telas e CSS retornaram HTTP 200 pelo WSGI do IRIS. Login, CSRF e alteração autenticada do TTL pela Production passaram. Inspeção visual das cinco telas com gestor e auditor.
- Reinício preservou seed READY, 540 observações, 40 experiências vetoriais, decisões, ledger e auditoria. Production voltou no estado 1. [Evidências do runtime](runtime-evidence.json).
- IPM 0.10.9: instância limpa, `CLEAN_APPLICATION_CLASSES 0`, Initialize/Validate/Compile/Activate SUCCESS e `IPM_APPLICATION_CLASSES 1`. [Carga limpa](ipm-clean.log), [Production/PEX após carga](ipm-runtime.log).

AutoML: MAE **1,85**, baseline **4,93**, 84 linhas de validação, corte cronológico e embargo de sete dias. Estes valores descrevem somente o histórico sintético. A busca vetorial repetida retornou os mesmos cinco IDs.

O aceite registrou sessões nativas com cinco ferramentas reais. Uma campanha exigiu uma tentativa de correção. Auditoria inclui tokens, cache, latência, sessões e correções. USD fica desconhecido enquanto os preços configuráveis não forem preenchidos; não é apresentado como zero.

## Matriz da SPEC

“Contrato” identifica testes isolados com fixtures/test doubles; “runtime” identifica execução no IRIS/Production real. A combinação não constitui validação clínica.

| ID | Evidência executada |
|---|---|
| T01 | Contrato altera SQLite institucional e consulta novamente; cenários do seed alteram origens por API e consultam pelo PEX, sem sincronização central |
| T02 | Runtime: Custom Adapter contra servidor descartável com resposta atrasada; resultado UNAVAILABLE sem quantidade inventada. Seed OFFLINE também passou |
| T03 | Runtime: CREATE/TRAIN/VALIDATE/PREDICT, versão do modelo, MAE e baseline no relatório |
| T04 | Runtime: histórico temporário censurado; forecast retorna stockout_affected e guard bloqueia qualidade insuficiente |
| T05 | Runtime: VECTOR_COSINE e duas buscas top-5 com mesmos IDs |
| T06 | Runtime: InventoryEventService → BPL → AIHubDecisionOperation; sessões nativas e message_trace no relatório |
| T07 | Contrato: alteração de quantidade, evidência desconhecida e omissão de campo obrigatório rejeitadas |
| T08 | Runtime: REQUEST_TRANSFER_FULL_WORKFLOW; aprovação, reserva revalidada, SupplyRequest e entrega |
| T09 | Contratos: retirada/bloqueio de saldo na origem antes da reserva e revalidação do domínio; nenhuma reserva insuficiente |
| T10 | Contrato FEFO e runtime EXPIRY_BLOCKS_TRANSFER |
| T11 | Runtime: DELIVERED com received_units=12 e used_units=0 |
| T12 | Contrato: janela curta bloqueia campanha; seed STOCKOUT remete necessidade urgente para revisão |
| T13 | Contrato: campanha confirmada impede novo candidato/convite sobreposto |
| T14 | Runtime: BO CampaignCreationOperation cria convites aprovados; IDs Java estáveis por campanha/destinatário |
| T15 | Runtime: FederatedInventoryOperation usa FederatedInventoryAdapter, inclusive timeout real |
| T16 | Runtime: tarefas EnsLib.Workflow por gestor/parceiro, aprovação/recusa e ledger; contrato rejeita papel/escopo indevidos |
| T17 | Runtime: aceite válido → CONFIRMED → processamento simulado → COMPLETED |
| T18 | Runtime: timer automático, 24h, consulta sem convite vencido e aceite tardio 409 |
| T19 | Runtime: timer expurga DecisionContext e PendingInvitation; DecisionAudit e ledger preservados |
| T20 | Runtime: outbox de expiração concluída uma vez; reavaliação operacional sem novo ciclo de convites |
| T21 | Contrato: doador sem opt-in bloqueado antes de chamar o BO Java |
| T22 | Contrato e runtime: OperationDefinition/Parameters/SupplyRequest/SupplyDelivery validados em R4 e trocados com origens |
| T23 | Runtime: NO_ACTION real no seed, sem proposta externa |
| T24 | Contrato com provider indisponível: 503 + ESCALATED, sem transferência/campanha e sem falso NO_ACTION. Respostas reais inválidas também foram bloqueadas durante desenvolvimento |
| T25 | Runtime: retorno após parada dos containers e atualização de imagem; decisões identificadas do aceite e volumes preservados |
| T26 | Runtime: instalação IPM limpa no mesmo build, ativação, início da Production e consulta PEX |
| T27 | Contrato: convite de instituição diferente retorna 403 antes de qualquer mutação |
| T28 | Painel real: K1–K6, referência anterior à decisão versus consulta atual com mesma previsão; hipótese/simulação explicitadas, recebidas e utilizadas separadas |

## Reprodução

Usar os comandos de instalação/teste do [README](../README.md). O seed é executado **depois** da aplicação funcional; o gate anterior ao seed está em [e2e-gate.json](e2e-gate.json). Não executar `e2e_fixture.script` sobre uma rede preenchida.

Relatórios novos ficam em `/durable/hemoflow-evidence`, sem depender de escrita na imagem. O teste do seed usa os controles reais da demo, cria backups, preserva auditoria/ledger e restaura o inventário sintético ao terminar. Não executar durante uma apresentação. Chamadas OpenAI têm custo.

## Limites explícitos

- Imagem Community AI Hub: FHIR R4 customizado e validado; **nenhuma alegação de repositório FHIR nativo for Health**.
- Correção AutoML e trampolins do Agent são específicos do EAP154; [patch e reversão](EAP154_PATCH.md). IRISLIB permanece sem modificação.
- A comparação K1/K2 usa observações antes/depois com a mesma previsão; não é experimento causal. K2 mede exposição potencial em 72h, não bolsas comprovadamente salvas.
- IPM foi instalado/testado localmente; módulo não publicado em registry. Compose é a distribuição completa.
- Visual Trace está disponível no portal pela correlação/sessão; o relatório exporta cabeçalhos reais das mensagens, sem alegar captura de tela do portal.

## Orquestração causal do AI Hub — 30/10/2026

Build 154U: classes/BPL compilados e Production reiniciada. Suíte Embedded Python: **56 passed**, `PYTEST_EXIT 0`. Aceite real, executado sequencialmente com LLM e simuladores: **12 cenários aprovados**, incluindo transferência completa, campanha completa, NO_ACTION, rede indisponível, falta urgente, validade inviável, recusa, convite expirado, TTL automático, reavaliação única e restauração segura. UI/API: cinco telas, assets, acesso, rotas e projeção multigrupo aprovados.

`tools/test_orchestration.py` confirmou agente → cinco Tools → PEX → guard → ramo correto na mesma sessão: transferência **4427** (32 mensagens), campanha **4480** (42 mensagens, incluindo a resposta posterior do alarme). Ver [trace completo](orchestration-trace.json) e [aceite](orchestration-acceptance.json). O teste também rejeita propostas associadas a NO_ACTION/revisão. Os prints foram atualizados em 30/10/2026 com as sessões 4427 e 4480; ver docs/screenshots/README.md para a proveniência e os limites da captura.

Testes de política incluem cobertura parcial, conciliação FEFO entre ofertas, campanha desnecessária e evidências atuais. Testes de comando incluem revisão obsoleta e deduplicação de avaliação concluída/em andamento. Injeção de queda de processo em cada fronteira de publicação/recuperação não foi executada nesta rodada.

