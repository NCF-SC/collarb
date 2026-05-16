import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# ==========================================
# 0. INICIALIZAÇÃO DA MEMÓRIA DO APP (Session State)
# ==========================================
if 'historico_rolagens' not in st.session_state:
    st.session_state['historico_rolagens'] = []
if 'caixa_acumulado_calls' not in st.session_state:
    st.session_state['caixa_acumulado_calls'] = 0.0
if 'mes_operacao' not in st.session_state:
    st.session_state['mes_operacao'] = 1
if 'preco_acao_tela' not in st.session_state:
    st.session_state['preco_acao_tela'] = 50.03
if 'simulador_preco' not in st.session_state:
    st.session_state['simulador_preco'] = 50.03

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

st.title("Gouldian Invest | Painel Quantitativo")
st.markdown("Gestão de Collar Dinâmico: Descasamento de Vencimentos, Amortização e Relatório Imutável com Retenção Fiscal.")
st.markdown("---")

# ==========================================
# 2. BARRA LATERAL (Monitor, Custos e Selic)
# ==========================================
st.sidebar.header("🔍 Monitor de Mercado")

ticker_acao = st.sidebar.text_input("Ticker da Ação", value="PETR4.SA")
st.sidebar.markdown(f"**Preço de Tela Atual:** R$ {st.session_state['preco_acao_tela']:.2f}")

if st.sidebar.button("Cotar Ação"):
    try:
        acao = yf.Ticker(ticker_acao)
        preco_atual = acao.history(period="1d")['Close'].iloc[-1]
        st.session_state['preco_acao_tela'] = float(preco_atual)
        st.session_state['simulador_preco'] = float(preco_atual) 
        st.rerun()
    except:
        st.sidebar.error("Erro ao buscar cotação da ação.")

st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Custos Operacionais e IR", expanded=False):
    ir_opcoes = st.number_input("Imposto de Renda (%)", value=15.0, step=0.5) / 100
    emol_acao = st.number_input("Emolumentos Ação (%)", value=0.0325, format="%.4f") / 100
    emol_opcao = st.number_input("Emolumentos Opção (%)", value=0.0375, format="%.4f") / 100
    corretagem = st.number_input("Custo de Corretagem (R$ por ordem)", value=0.00, step=1.0)
    taxa_ex_b3 = st.number_input("Taxa de Exercício B3 (%)", value=0.5, step=0.1) / 100

with st.sidebar.expander("🏦 Benchmark e Juros", expanded=True):
    juros_bruto_aa = st.number_input("Taxa Selic Bruta (% a.a.)", value=14.50, step=0.1) / 100
    ir_renda_fixa = st.number_input("IR sobre Renda Fixa (%)", value=22.5, step=0.5) / 100

juros_liquido_aa = juros_bruto_aa * (1 - ir_renda_fixa)
juros_liquido_am = juros_liquido_aa / 12
meta_mensal = juros_liquido_am * 100

st.sidebar.markdown("---")


# ==========================================
# 3. FASE 1: AQUISIÇÃO, SEGURO LONGO E ALVO
# ==========================================
st.header(f"📦 Fase 1: Aquisição e Amortização (Mês {st.session_state['mes_operacao']})")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. Ativo Base")
    preco_acao = st.number_input("Preço de Compra da Ação (R$)", value=st.session_state.get('preco_acao_tela', 50.03), format="%.2f")
    qtd = st.number_input("Quantidade", value=1000, step=100)

with col2:
    st.subheader("2. Seguro Longo (Put)")
    ticker_put = st.text_input("Código da Put", value="PETRR454")
    
    if st.button("Cotar Put"):
        try:
            put_obj = yf.Ticker(f"{ticker_put}.SA")
            hist_put = put_obj.history(period="1d")
            if not hist_put.empty:
                st.session_state['preco_put_tela'] = float(hist_put['Close'].iloc[-1])
                st.success(f"Put Mercado: R$ {st.session_state['preco_put_tela']:.2f}")
            info_put = put_obj.info
            if 'expireDate' in info_put and info_put['expireDate'] is not None:
                st.session_state['venc_put_tela'] = datetime.datetime.fromtimestamp(info_put['expireDate']).date()
        except:
            st.warning("Aviso: Falha na API. Preencha manualmente.")

    preco_put = st.number_input("Prêmio Pago na Put (R$)", value=st.session_state.get('preco_put_tela', 3.43), format="%.2f")
    strike_put = st.number_input("Strike da Put (R$)", value=49.46, format="%.2f")
    vencimento_put = st.date_input("Vencimento da Put Longa", value=st.session_state.get('venc_put_tela', datetime.date.today() + datetime.timedelta(days=365)))

# Cálculos de Montagem
volume_acao = preco_acao * qtd
volume_put = preco_put * qtd
tx_b3_entrada_acao = volume_acao * emol_acao
tx_b3_entrada_put = volume_put * emol_opcao
corretagem_fase1 = (corretagem * 2) if corretagem > 0 else 0.0 
taxas_iniciais_totais = tx_b3_entrada_acao + tx_b3_entrada_put + corretagem_fase1

custo_base_bruto = volume_acao + volume_put + taxas_iniciais_totais
custo_base_ajustado = custo_base_bruto - st.session_state['caixa_acumulado_calls']

strike_minimo = (custo_base_ajustado / qtd) / (1 - taxa_ex_b3)
preco_medio_atual = custo_base_ajustado / qtd
meta_financeira_12m = custo_base_bruto * (1 + juros_liquido_aa)

with col3:
    st.subheader("3. Gestão de Risco e Alvo")
    st.info(f"**Caixa LÍQUIDO Acumulado Reinvestido:** R$ {st.session_state['caixa_acumulado_calls']:,.2f}")
    st.metric("Custo Base AJUSTADO", f"R$ {custo_base_ajustado:,.2f}", f"Médio Atual: R$ {preco_medio_atual:.2f}", delta_color="inverse")
    st.warning(f"🎯 **Strike MÍNIMO para Call:** R$ {strike_minimo:.2f}")
    st.info(f"💰 **Alvo de Renda Fixa (12M):** R$ {meta_financeira_12m:,.2f}")

st.markdown("---")

# ==========================================
# 4. FASE 2: REMUNERAÇÃO (CALL CURTA)
# ==========================================
st.header("⚡ Fase 2: Remuneração Mensal (Call Curta)")
col4, col5 = st.columns([1, 2])

with col4:
    ticker_call = st.text_input("Código da Call", value="PETRF54")
    
    if st.button("Cotar Call"):
        try:
            call_obj = yf.Ticker(f"{ticker_call}.SA")
            hist_call = call_obj.history(period="1d")
            if not hist_call.empty:
                st.session_state['preco_call_tela'] = float(hist_call['Close'].iloc[-1])
                st.success(f"Call Mercado: R$ {st.session_state['preco_call_tela']:.2f}")
            info_call = call_obj.info
            if 'expireDate' in info_call and info_call['expireDate'] is not None:
                st.session_state['venc_call_tela'] = datetime.datetime.fromtimestamp(info_call['expireDate']).date()
        except:
            st.warning("Aviso: Falha na API. Preencha manualmente.")

    strike_call = st.number_input("Strike da Call Selecionada (R$)", value=54.19, format="%.2f")
    premio_call = st.number_input("Prêmio Bruto Recebido (R$)", value=st.session_state.get('preco_call_tela', 0.25), format="%.2f")
    vencimento_call = st.date_input("Vencimento da Call Curta", value=st.session_state.get('venc_call_tela', datetime.date.today() + datetime.timedelta(days=30)))

volume_call = premio_call * qtd
tx_b3_entrada_call = volume_call * emol_opcao
corretagem_fase2 = corretagem if corretagem > 0 else 0.0

# Custos isolados da Call para a rolagem caso ela vire pó
receita_liquida_call_pre_ir = volume_call - tx_b3_entrada_call - corretagem_fase2
ir_isolado_call_po = receita_liquida_call_pre_ir * ir_opcoes
receita_realmente_liquida_call = receita_liquida_call_pre_ir - ir_isolado_call_po

with col5:
    st.write("")
    st.write("")
    st.success(f"💰 Prêmio Líquido Creditado na Conta (D+1): **R$ {receita_liquida_call_pre_ir:,.2f}**")
    st.caption(f"*(Se esta Call virar pó, a DARF deste mês será de R$ {ir_isolado_call_po:,.2f}, sobrando R$ {receita_realmente_liquida_call:,.2f} líquidos para amortizar o preço médio)*")
    if strike_call < strike_minimo:
        st.error("⚠️ STRIKE DA CALL ABAIXO DO MÍNIMO!")

st.markdown("---")

# ==========================================
# 5. FASE 3: SIMULADOR DE PAYOFF E DRE
# ==========================================
st.header("🔮 Fase 3: Simulador de Payoff no Vencimento da Call")

# 1. Definimos o limite máximo do slider (100% de alta = dobro do preço de compra)
max_slider = float(preco_acao * 2.0)

# 2. Proteção do Streamlit: Garante que o valor padrão não ultrapasse o max_value atual
valor_default = st.session_state.get('simulador_preco', float(preco_acao))
if valor_default > max_slider:
    valor_default = max_slider

# 3. Slider ajustado dinamicamente ao Preço de Compra (preco_acao)
preco_vencimento = st.slider(
    "Preço do Ativo no Vencimento da Call (R$)", 
    min_value=0.0, 
    max_value=max_slider, 
    value=float(valor_default),
    step=0.10
)

# Atualiza a memória com o valor movido no slider
st.session_state['simulador_preco'] = preco_vencimento

if preco_vencimento > strike_put:
    valor_residual_put = 0.0
    st.caption("ℹ️ *Ativo acima do Strike da Put: Valor residual de proteção zerado no Payoff.*")
else:
    valor_residual_put = st.number_input("Valor de Tela da Put no Mercado (R$)", value=2.00, format="%.2f")

receita_venda_put_residual = valor_residual_put * qtd

deseja_exercer_put = False
if preco_vencimento <= strike_put:
    deseja_exercer_put = st.checkbox("🎯 Deseja exercer a Put de Proteção neste cenário de queda?", value=False)

# Cenários de Liquidação
if preco_vencimento >= strike_call:
    cenario_nome = "🚀 EXERCIDO NA CALL (Alta)"
    receita_venda_ativo = strike_call * qtd
    taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
    corretagem_saida = corretagem if corretagem > 0 else 0.0
    status_put = "Ficou fora do dinheiro (Virou pó / Custo perdido)"
    status_call = f"Exercida a R$ {strike_call:.2f}"
    receita_venda_put_residual = 0.0 

elif deseja_exercer_put:
    cenario_nome = "🛡️ PROTEGIDO POR EXERCÍCIO DA PUT (Decisão do Usuário)"
    receita_venda_ativo = strike_put * qtd  
    taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
    corretagem_saida = corretagem if corretagem > 0 else 0.0
    status_put = f"Exercida voluntariamente a R$ {strike_put:.2f}"
    status_call = "Venceu sem valor (Virou Pó)"
    receita_venda_put_residual = 0.0  

else:
    cenario_nome = "⚖️ POSIÇÃO MANTIDA / LATERALIZOU (Decisão do Usuário)"
    receita_venda_ativo = preco_vencimento * qtd 
    taxa_saida_b3 = receita_venda_ativo * emol_acao 
    corretagem_saida = corretagem if corretagem > 0 else 0.0
    status_put = f"Mantida na carteira (Valorizada em tela por R$ {valor_residual_put:.2f})"
    status_call = "Venceu sem valor (Virou Pó)"

# Cálculo Tributário Geral do Payoff
lucro_bruto_operacao = (receita_venda_ativo + receita_liquida_call_pre_ir + receita_venda_put_residual) - (custo_base_ajustado + taxa_saida_b3 + corretagem_saida)
ir_devido = max(0.0, lucro_bruto_operacao * ir_opcoes)
lucro_liquido_final = lucro_bruto_operacao - ir_devido

rentabilidade_liquida = (lucro_liquido_final / custo_base_bruto) * 100 
meta_acumulada_mes = meta_mensal * st.session_state['mes_operacao']

st.markdown(f"#### Cenário Operacional Identificado: **{cenario_nome}**")

c_res1, c_res2, c_res3 = st.columns(3)
c_res1.metric("Lucro Líquido Final da Estrutura", f"R$ {lucro_liquido_final:,.2f}")
c_res2.metric("Rentabilidade Líquida Global", f"{rentabilidade_liquida:.2f}%")
c_res3.metric(f"Meta Selic Acumulada no Período", f"{meta_acumulada_mes:.2f}%")

total_entradas = receita_venda_ativo + receita_liquida_call_pre_ir + st.session_state['caixa_acumulado_calls'] + receita_venda_put_residual
total_saidas = volume_acao + volume_put + taxas_iniciais_totais + taxa_saida_b3 + corretagem_saida + ir_devido

with st.expander("🔎 Ver Raio-X Detalhado do Simulado (DRE Completo)", expanded=True):
    st.markdown(f"""
    **1. Demonstração de Fluxo dos Derivativos:**
    * **Seguro Longo ({ticker_put}):** {status_put}
    * **Renda Curta ({ticker_call}):** {status_call}
    
    **2. Fluxo de Caixa (Entradas Realizadas + Projetadas):**
    * (+) Valor de Liquidação/Mercado do Ativo (Ação): R$ {receita_venda_ativo:,.2f}
    * (+) Prêmio Líquido Capturado na Call deste Mês (Pré-IR): R$ {receita_liquida_call_pre_ir:,.2f}
    * (+) Valor de Recuperação da Put Residual (Venda de Tela): R$ {receita_venda_put_residual:,.2f}
    * (+) Caixa Líquido de Rolagens Anteriores (Já descontado IR passado): R$ {st.session_state['caixa_acumulado_calls']:,.2f}
    * **TOTAL DE ENTRADAS DO CICLO: R$ {total_entradas:,.2f}**
    
    **3. Fluxo de Caixa (Saídas e Custos Históricos Completos):**
    * (-) Desembolso de Compra da Ação: R$ {volume_acao:,.2f}
    * (-) Desembolso de Compra da Put (Prêmio Inicial): R$ {volume_put:,.2f}
    * (-) Custos de Atrito Iniciais (B3 + Corretagens Entrada): R$ {taxas_iniciais_totais:,.2f}
    * (-) Taxas de Liquidação / Exercício de Saída B3: R$ {taxa_saida_b3:,.2f}
    * (-) Taxa de Corretagem de Encerramento: R$ {corretagem_saida:,.2f}
    * (-) Guia de Imposto de Renda Estimada (DARF 15%): R$ {ir_devido:,.2f}
    * **TOTAL DE SAÍDAS DO CICLO: R$ {total_saidas:,.2f}**
    
    **4. Lucro Líquido Real (Entradas - Saídas):**
    * **LUCRO LÍQUIDO FINAL DO COLLAR = R$ {lucro_liquido_final:,.2f}**
    """)

st.markdown("---")

# ==========================================
# 6. FASE 4: AUDITORIA HISTÓRICA DE ROLAGENS
# ==========================================
st.header("⏳ Fase 4: Relatório Histórico de Rolagens")
st.write("Se a Call virar pó, clique abaixo. O sistema já vai descontar os 15% de IR da opção automaticamente antes de abater seu preço médio.")

c_btn1, c_btn2 = st.columns(2)

with c_btn1:
    if st.button("➕ Call Virou Pó: Registrar Lucro e Rolar Mês", use_container_width=True):
        novo_registro = {
            "Mês": st.session_state['mes_operacao'],
            "Código Call": ticker_call,
            "Vencimento Call": vencimento_call.strftime("%d/%m/%Y"),
            "Strike": strike_call,
            "Prêmio Retido (Pós-B3)": receita_liquida_call_pre_ir,
            "DARF do Mês (15%)": ir_isolado_call_po,
            "Amortização Líquida Real": receita_realmente_liquida_call,
            "Preço Médio Ajustado": preco_medio_atual - (receita_realmente_liquida_call / qtd),
            "Meta Selic Mês (%)": meta_mensal,  
            "Retorno Líquido Mês (%)": (receita_realmente_liquida_call / custo_base_ajustado) * 100
        }
        st.session_state['historico_rolagens'].append(novo_registro)
        st.session_state['caixa_acumulado_calls'] += receita_realmente_liquida_call
        st.session_state['mes_operacao'] += 1
        st.rerun()

with c_btn2:
    if st.button("🛑 Fim de Estrutura: Encerrar e Zerar Histórico", type="primary", use_container_width=True):
        st.session_state['historico_rolagens'] = []
        st.session_state['caixa_acumulado_calls'] = 0.0
        st.session_state['mes_operacao'] = 1
        st.session_state['simulador_preco'] = st.session_state['preco_acao_tela']
        st.rerun()

if st.session_state['historico_rolagens']:
    st.subheader("📊 Relatório de Auditoria — Gouldian Invest")
    df_historico = pd.DataFrame(st.session_state['historico_rolagens'])
    
    df_historico['Strike'] = df_historico['Strike'].apply(lambda x: f"R$ {x:.2f}")
    df_historico['Prêmio Retido (Pós-B3)'] = df_historico['Prêmio Retido (Pós-B3)'].apply(lambda x: f"R$ {x:.2f}")
    df_historico['DARF do Mês (15%)'] = df_historico['DARF do Mês (15%)'].apply(lambda x: f"R$ {x:.2f}")
    df_historico['Amortização Líquida Real'] = df_historico['Amortização Líquida Real'].apply(lambda x: f"R$ {x:.2f}")
    df_historico['Preço Médio Ajustado'] = df_historico['Preço Médio Ajustado'].apply(lambda x: f"R$ {x:.2f}")
    df_historico['Meta Selic Mês (%)'] = df_historico['Meta Selic Mês (%)'].apply(lambda x: f"{x:.2f}%")
    df_historico['Retorno Líquido Mês (%)'] = df_historico['Retorno Líquido Mês (%)'].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(df_historico, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("Gouldian Invest — Excelência em Engenharia Financeira de Derivativos.")