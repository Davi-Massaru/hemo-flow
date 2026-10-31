# Mapa de tecnologias — HemoFlow MVP v5.0

> Documento de consulta derivado da seção 3 da SPEC. A SPEC.md é a fonte normativa.

## 3. Mapa de todas as tecnologias InterSystems e componentes necessários

**Este mapa é normativo e também existe em `SPEC/MAPA_TECNOLOGIAS.md`.** Os bônus abaixo são apenas potenciais; exigem implementação e prova na Production ou publicação conforme o regulamento.

| Tecnologia | Problema que resolve | WF-01 transferência | WF-02 campanhas | Prova técnica / bônus potencial |
|---|---|---|---|---|
| **IRIS for Health / SQL / `%Persistent`** | Dados de histórico, solicitações, configurações e auditoria | `Transfer` e trilha | `Campaign`, `InvitationLedger` | SQL e persistência verificáveis |
| **IRIS Interoperability (BS/BP/BPL/BO)** | Entrada, roteamento, mensagens, tratamento de erro e observabilidade | Consultar B/C e executar fluxo de fornecimento | Solicitar, aprovar, enviar e receber respostas | Visual Trace dos dois workflows; requisito do concurso |
| **AI Hub / `%AI.Agent` + ToolSet** | Escolher uma das três estratégias com justificativa e evidências | Seleciona origem/quantidade permitida ou não agir | Decide necessidade, parceiro e janela viáveis | Sessão/Tool calls/decisão correlacionadas no workflow; requisito central |
| **IntegratedML + AutoML** | Prever consumo de 7 dias, com qualidade identificada | Detecta déficit futuro de A | Evita campanhas sem necessidade e dimensiona meta | Treino, backtest, modelo e chamada SQL real |
| **IRIS Vector Search** | Recuperar campanhas encerradas semelhantes para orientar parceiros | Não usado para buscar números de estoque | Busca semântica com filtros e resultado medido | SQL `VECTOR_COSINE`, top-K e referências; **+2** |
| **FHIR R4 / IRIS for Health** | Contratos entre organizações sem compartilhar banco | Operação customizada `Parameters` e `SupplyRequest`/`SupplyDelivery` | `Organization` / `Location` para cadastro quando aplicável | Exemplos validados em R4 e duas fontes independentes |
| **Java PEX** | Materializar planos de convites como BO da Production | BO Java para operação de consulta federada | `CampaignCreationOperation` Java PEX | Classes Java registradas e chamadas pela Production; **+3** |
| **Custom Outbound Adapter** | Encapsular protocolo de disponibilidade FHIR dos centros | `FederatedInventoryAdapter` usado pela BO | — | Adapter próprio ativo na Production; **+2** |
| **IRIS Workflow Engine** | Encaminhar aprovações humanas e registrar resposta | Aprovação da origem | Aprovação do hemocentro e aceite institucional | Tarefas reais, recusa, aceite e timeout; **+2** |
| **Embedded Python / PyProd** | Preparação de dados, validações, API e expiração | Orquestra entradas/cálculos determinísticos | Regras, registro de convites, TTL | Código executado dentro IRIS; **+3** |
| **`%Dictionary` + classe-base TTL** | Metadados de classes e política reutilizável de expiração | Contextos técnicos transitórios | Convites de 24h | Duas classes expirando sem apagar auditoria; candidato **DPI-I-393 +4**, sujeito à avaliação |
| **WSGI / Flask** | Painel e APIs enxutas hospedadas no IRIS | Gatilhos e aprovações | Caixa de convites | Interface funcional autenticada |
| **Docker / Compose** | Subir IRIS + dois hemocentros simulados independentes | Demonstra consulta federada real | Executa aplicação | Build e restart com volumes; **+2** |
| **IPM/ZPM** | Instalar o produto reproduzivelmente | Classes/Production | Classes/PEX/arquivos | Pacote instalado e publicado; **+2 se atendidas exigências** |

**Limite:** Java PEX tem duas responsabilidades técnicas pequenas e justificadas. PyProd/Embedded Python não é tratado como bônus Java PEX. AI Hub/AutoML/Vector Search são recursos diferentes; similaridade não significa previsão nem autorização.


## Evidências transversais

- **Interoperability:** evento → Tool AI Hub → retorno → DecisionGuard → WF-01/WF-02 → conclusão no Visual Trace.
- **AutoML:** `TRAIN MODEL`/`VALIDATE MODEL` + versão do modelo e MAE real.
- **Vector Search:** consulta `VECTOR_COSINE` retornando IDs de campanhas reais do corpus sintético.
- **Java PEX:** chamada de `CampaignCreationOperation` e uso efetivo do `FederatedInventoryAdapter` pela Production.
- **Workflow Engine:** tarefas com usuário, aceite, recusa e prazo.
- **TTL:** convite expirado some de Pendentes e não pode ser aceito; ledger/auditoria permanecem.
- **FHIR:** operação própria declarada com `OperationDefinition`; `SupplyRequest`/`SupplyDelivery` R4 válidos.
- **Métrica assistencial:** reportar déficit, desperdício evitável estimado, datas e unidades confirmadas, sem confundir intenção com produto liberado.
