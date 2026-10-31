# EAP 154: correção local de PREDICT

O código exportado do build `2026.3.0AI.154.0` contém dois wrappers `%PredictAll`
que usam `tsm` sem declará-lo. O SQL retorna `-400` com
`<UNDEFINED>%PredictAll+5^%ML.AutoML.TrainedModel.1 *tsm`.

Diff idêntico em `%ML.AutoML.TrainedModel` e `%ML.AutoML.Provider`:

```diff
- ...expr,$G(mtorder),$G(mtunary),tsm)
+ ...expr,$G(mtorder),$G(mtunary),$G(tsm))
```

Os métodos internos `%PredictAll0` já definem `tsm:%Integer=0`.

`tools/patch_eap154.script` exporta as três classes do pacote, verifica build e
fontes e cria um **mapeamento de `%ML.AutoML` somente no namespace USER para o
banco USER da aplicação**. A cópia corrigida é compilada ali. Nenhuma classe do
IRISLIB é alterada e suas proteções permanecem originais. A delegação aos métodos
originais `%SYS.SQLSRV` é mantida.

O build e o bootstrap executam o script. O original fica em
`/durable/hemoflow-eap154-original.xml`. Após validar um build corrigido, remover
o mapeamento de pacote da aplicação e as classes locais; os originais do IRISLIB
continuam disponíveis. Não remover esse mapeamento enquanto o build 154 estiver
em uso. Não tratar o runtime com override como distribuição oficial corrigida.

## Consulta analítica após recompilação

Na validação da UI em 30/10/2026, a consulta em lote `PREDICT` sobre `DemandFeature` reproduziu `INVALID OREF` após recompilar as classes persistentes. A auditoria lê o conjunto de validação e executa `PREDICT` parametrizado pelas features, usando a mesma função de inferência do dashboard e deduplicando vetores de features durante a requisição. O modelo continua sendo o IntegratedML real; não há série sintética de fallback. A suíte HTTP exige um conjunto de validação não vazio, além de ausência de erros, para evitar aprovação de um gráfico vazio.
