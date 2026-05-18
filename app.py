import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import hashlib
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO DE BANCO DE DADOS E SEGURANÇA
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

@st.cache_resource
def init_connection():
    # Puxa as chaves cadastradas na aba "Secrets" do Streamlit Cloud
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Erro ao conectar ao Banco de Dados. Verifique os Secrets do Streamlit.")
    st.stop()

def hash_senha(senha):
    """Criptografa a senha para não ficar exposta no banco de dados"""
    return hashlib.sha256(senha.encode()).hexdigest()

# ==========================================
# 1. INICIALIZAÇÃO DA MEMÓRIA
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""

def zerar_dados_financeiros():
    st.session_state['historico_rolagens'] = []
    st.session_state['caixa_acumulado_calls'] = 0.0
    st.session_state['caixa_proventos'] = 0.0
    st.session_state['mes_operacao'] = 1
    st.session_state['preco_acao_tela'] = 0.0
    st.session_state['simulador_preco'] = 0.0

if 'historico_rolagens' not in st.session_state:
    zerar_dados_financeiros()

# ==========================================
# 2. TELA DE LOGIN / CADASTRO
# ==========================================
if not st.session_state['logged_in']:
    st.title("🦅 Gouldian Invest")
    st.markdown("Gestão Profissional de Collar Dinâmico e Derivativos.")
    
    col_login, col_vazia = st.columns([1, 2])
    with col_login:
        st.subheader("Acesso ao Painel")
        modo = st.radio("Selecione:", ["Login", "Criar Conta"], horizontal=True)
        
        email_input = st.text_input("E-mail").strip().lower()
        senha_input = st.text_input("Senha", type="password")
        
        if modo == "Login":
            if st.button("Entrar", type="primary", use_container_width=True):
                if email_input and senha_input:
                    senha_criptografada = hash_senha(senha_input)
                    # Busca usuário no banco
                    resposta = supabase.table("usuarios").select("*").eq("email", email_input).execute()
                    
                    if len(resposta.data) > 0:
                        user_db = resposta.data[0]
                        if user_db["senha"] == senha_criptografada:
                            st.session_state['logged_in'] = True
                            st.session_state['user_email'] = email_input
                            
                            # Carrega dados salvos
                            dados_salvos = user_db.get("dados", {})
                            if dados_salvos:
                                st.session_state['historico_rolagens'] = dados_salvos.get('historico_rolagens', [])
                                st.session_state['caixa_acumulado_calls'] = dados_salvos.get('caixa_acumulado_calls', 0.0)
                                st.session_state['caixa_proventos'] = dados_salvos.get('caixa_proventos', 0.0)
                                st.session_state['mes_operacao'] = dados_salvos.get('mes_operacao', 1)
                            
                            st.rerun()
                        else:
                            st.error("Senha incorreta.")
                    else:
                        st.error("Usuário não encontrado. Crie uma conta.")
                else:
                    st.warning("Preencha e-mail e senha.")
                    
        else:
            if st.button("Cadastrar", type="primary", use_container_width=True):
                if email_input and senha_input:
                    verifica = supabase.table("usuarios").select("email").eq("email", email_input).execute()
                    if len(verifica.data) > 0:
                        st.error("Este e-mail já está cadastrado.")
                    else:
                        senha_criptografada = hash_senha(senha_input)
                        novo_user = {
                            "email": email_input,
                            "senha": senha_criptografada,
                            "dados": {}
                        }
                        supabase.table("usuarios").insert(novo_user).execute()
                        st.success("Conta criada com sucesso! Mude para 'Login' e acesse.")
                else:
                    st.warning("Preencha e-mail e senha para cadastrar.")
    
    st.stop() # Trava a execução até logar

# ==========================================
# TELA PRINCIPAL (APÓS LOGIN)
# ==========================================
st.title("Gouldian Invest | Painel Quantitativo")
st.markdown("Gestão de Collar Dinâmico: Descasamento de Vencimentos, Amortização, Proventos e Rentabilidade sobre Capital Inicial.")

col_user1, col_user2, col_user3 = st.columns([3, 1, 1])
nome_exibicao = st.session_state['user_email'].split('@')[0].capitalize()
col_user1.write(f"Bem-vindo(a), **{nome_exibicao}**! Seus estudos estão sincronizados na nuvem ☁️")

if col_user2.button("💾 Salvar Estudo na Nuvem", type="primary"):
    dados_para_nuvem = {
        "historico_rolagens": st.session_state['historico_rolagens'],
        "caixa_acumulado_calls": st.session_state['caixa_acumulado_calls'],
        "caixa_proventos": st.session_state['caixa_proventos'],
        "mes_operacao": st.session_state['mes_operacao']
    }
    supabase.table("usuarios").update({"dados": dados_para_nuvem}).eq("email", st.session_state['user_email']).execute()
    st.success("Progresso salvo com sucesso!")

if col_user3.button("Sair da Conta"):
    st.session_state['logged_in'] = False
    zerar_dados_financeiros()
    st.rerun()

st.markdown("---")

# ==========================================
# BARRA LATERAL (Monitor, Custos e Selic)
# ==========================================
st.sidebar.header("🔍 Monitor de Mercado")

ticker_acao = st.sidebar.text_input("Ticker da Ação", value="", placeholder="Ex: PETR4.SA")
st.sidebar.markdown(f"**Preço de Tela Atual:** R$ {st.session_state['preco_acao_tela']:.2f}")

if st.sidebar.button("Cotar Ação"):
    if ticker_acao:
        try:
            acao = yf.Ticker(ticker_acao)
            preco_atual = acao.history(period="1d")['Close'].iloc[-1]
            st.session_state['preco_acao_tela'] = float(preco_atual)
            st.session_state['simulador_preco'] = float(preco_atual) 
            st.rerun()
        except:
            st.sidebar.error("Erro ao buscar cotação. Verifique o Ticker.")

st.sidebar.markdown("---")

with st.sidebar.expander("⚙️ Custos Operacionais e IR", expanded=False):
    ir_opcoes = st.number_input("Imposto de Renda Opções (%)", value=15.0, step=0.5) / 100
    ir_jscp_tax = st.number_input("Imposto de Renda JSCP (%)", value=15.0, step=0.5) / 100
    emol_acao = st.number_input("Emolumentos Ação (%)", value=0.0325, format="%.4f") / 100
    emol_opcao = st.number_input("Emolumentos Opção (%)", value=0.0375, format="%.4f") / 100
    corretagem = st.number_input("Custo de Corretagem (R$)", value=0.00, step=1.0)
    taxa_ex_b3 = st.number_input("Taxa de Exercício B3 (%)", value=0.5, step=0.1) / 100

with st.sidebar.expander("🏦 Benchmark e Juros", expanded=False):
    juros_bruto_aa = st.number_input("Taxa Selic Bruta (% a.a.)", value=14.50, step=0.1) / 100
    ir_renda_fixa = st.number_input("IR sobre Renda Fixa (%)", value=22.5, step=0.5) / 100
    juros_liquido_aa = juros_bruto_aa * (1 - ir_renda_fixa)
    tipo_juros = st.radio("Cálculo da Taxa Mensal", ["Simples (Conservador)", "Composto (Equivalente)"])
    if "Simples" in tipo_juros:
        juros_liquido_am = juros_liquido_aa / 12
    else:
        juros_liquido_am = ((1 + juros_liquido_aa) ** (1/12)) - 1
    meta_mensal = juros_liquido_am * 100

st.sidebar.markdown("---")

# ==========================================
# FASE 1: AQUISIÇÃO, SEGURO LONGO E ALVO
# ==========================================
st.header(f"📦 Fase 1: Aquisição e Amortização (Mês {st.session_state['mes_operacao']})")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. Ativo Base")
    preco_acao = st.number_input("Preço de Compra da Ação (R$)", value=st.session_state.get('preco_acao_tela', 0.0), format="%.2f")
    qtd = st.number_input("Quantidade", value=0, step=100)

with col2:
    st.subheader("2. Seguro Longo (Put)")
    ticker_put = st.text_input("Código da Put", value="", placeholder="Ex: PETRR454")
    if st.button("Cotar Put"):
        if ticker_put:
            try:
                put_obj = yf.Ticker(f"{ticker_put}.SA")
                hist_put = put_obj.history(period="1d")
                if not hist_put.empty:
                    st.session_state['preco_put_tela'] = float(hist_put['Close'].iloc[-1])
                    st.success(f"Put Mercado: R$ {st.session_state['preco_put_tela']:.2f}")
            except:
                st.warning("Falha na API. Preencha manualmente.")

    preco_put = st.number_input("Prêmio Pago na Put (R$)", value=st.session_state.get('preco_put_tela', 0.0), format="%.2f")
    strike_put = st.number_input("Strike da Put (R$)", value=0.0, format="%.2f")

# Prevenção de divisão por zero e setup de variáveis padrões
volume_acao = volume_put = tx_b3_entrada_acao = tx_b3_entrada_put = corretagem_fase1 = taxas_iniciais_totais = 0.0
custo_base_bruto = custo_base_ajustado = strike_minimo = preco_medio_atual = 0.0
caixa_total_gerado = st.session_state['caixa_acumulado_calls'] + st.session_state['caixa_proventos']

if qtd > 0:
    volume_acao = preco_acao * qtd
    volume_put = preco_put * qtd
    tx_b3_entrada_acao = volume_acao * emol_acao
    tx_b3_entrada_put = volume_put * emol_opcao
    corretagem_fase1 = (corretagem * 2) if corretagem > 0 else 0.0 
    taxas_iniciais_totais = tx_b3_entrada_acao + tx_b3_entrada_put + corretagem_fase1

    custo_base_bruto = volume_acao + volume_put + taxas_iniciais_totais
    custo_base_ajustado = custo_base_bruto - caixa_total_gerado
    strike_minimo = (custo_base_ajustado / qtd) / (1 - taxa_ex_b3)
    preco_medio_atual = custo_base_ajustado / qtd

with col3:
    st.subheader("3. Gestão de Risco e Alvo")
    st.markdown(f"**Capital Inicial Investido:** R$ {custo_base_bruto:,.2f}")
    st.info(f"**Caixa LÍQUIDO Reinvestido:** R$ {caixa_total_gerado:,.2f}")
    st.metric("Custo Base AJUSTADO", f"R$ {custo_base_ajustado:,.2f}", f"Preço Médio: R$ {preco_medio_atual:.2f}", delta_color="inverse")
    st.warning(f"🎯 **Strike MÍNIMO Call:** R$ {strike_minimo:.2f}")

st.markdown("---")

# ==========================================
# FASE 2: REMUNERAÇÃO (CALL E PROVENTOS)
# ==========================================
st.header("⚡ Fase 2: Remuneração Mensal")

tab1, tab2 = st.tabs(["Lançamento de Call", "Dividendos e JSCP"])

with tab1:
    col4, col5 = st.columns([1, 2])
    with col4:
        ticker_call = st.text_input("Código da Call", value="", placeholder="Ex: PETRF54")
        strike_call = st.number_input("Strike da Call (R$)", value=0.0, format="%.2f")
        premio_call = st.number_input("Prêmio Bruto (R$)", value=0.0, format="%.2f")

    volume_call = premio_call * qtd
    receita_liquida_call_pre_ir = volume_call - (volume_call * emol_opcao) - (corretagem if corretagem > 0 else 0.0)
    ir_isolado_call_po = receita_liquida_call_pre_ir * ir_opcoes
    receita_realmente_liquida_call = receita_liquida_call_pre_ir - ir_isolado_call_po

    with col5:
        st.write("")
        st.success(f"💰 Prêmio Líquido D+1: **R$ {receita_liquida_call_pre_ir:,.2f}**")
        st.caption(f"*(Se virar pó, DARF: R$ {ir_isolado_call_po:,.2f} | Sobra: R$ {receita_realmente_liquida_call:,.2f} líquidos)*")
        if strike_call > 0 and strike_call < strike_minimo:
            st.error("⚠️ STRIKE ABAIXO DO MÍNIMO!")

with tab2:
    c_prov1, c_prov2, c_prov3 = st.columns(3)
    with c_prov1:
        dividendos_brutos = st.number_input("Dividendos Isentos (R$)", value=0.0, step=10.0)
    with c_prov2:
        jscp_bruto = st.number_input("JSCP Bruto (R$)", value=0.0, step=10.0)
    
    ir_jscp = jscp_bruto * ir_jscp_tax
    total_proventos_liquidos = dividendos_brutos + (jscp_bruto - ir_jscp)
    
    with c_prov3:
        st.info(f"Retenção 15% JSCP: **R$ -{ir_jscp:.2f}**")
        st.success(f"Proventos Líquidos: **R$ {total_proventos_liquidos:.2f}**")

st.markdown("---")

# ==========================================
# FASE 3 E 4: SIMULADOR E HISTÓRICO
# ==========================================
st.header("🔮 Fase 3: Simulador e Histórico")

max_slider = float(preco_acao * 2.0) if preco_acao > 0 else 100.0
valor_default = min(st.session_state.get('simulador_preco', float(preco_acao)), max_slider)

preco_vencimento = st.slider("Preço do Ativo no Vencimento da Call (R$)", min_value=0.0, max_value=max_slider, value=float(valor_default), step=0.10)
st.session_state['simulador_preco'] = preco_vencimento

if preco_vencimento > strike_put and strike_put > 0:
    valor_residual_put = 0.0
    st.caption("ℹ️ *Ativo acima do Strike da Put: Valor residual zerado no Payoff.*")
else:
    valor_residual_put = st.number_input("Valor de Tela da Put no Mercado (R$)", value=0.0, format="%.2f")

receita_venda_put_residual = valor_residual_put * qtd
deseja_exercer_put = False
if preco_vencimento <= strike_put and strike_put > 0:
    deseja_exercer_put = st.checkbox("🎯 Deseja exercer a Put de Proteção neste cenário de queda?", value=False)

# Configurações padrão para evitar erros visuais se QTD for 0
receita_venda_ativo = taxa_saida_b3 = corretagem_saida = 0.0
cenario_nome = "Aguardando preenchimento"

if qtd > 0:
    if preco_vencimento >= strike_call and strike_call > 0:
        cenario_nome = "🚀 EXERCIDO NA CALL (Alta)"
        receita_venda_ativo = strike_call * qtd
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        receita_venda_put_residual = 0.0 

    elif deseja_exercer_put:
        cenario_nome = "🛡️ PROTEGIDO POR EXERCÍCIO DA PUT"
        receita_venda_ativo = strike_put * qtd  
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        receita_venda_put_residual = 0.0  

    else:
        cenario_nome = "⚖️ POSIÇÃO MANTIDA / LATERALIZOU"
        receita_venda_ativo = preco_vencimento * qtd 
        taxa_saida_b3 = receita_venda_ativo * emol_acao 
        corretagem_saida = corretagem if corretagem > 0 else 0.0

lucro_bruto_operacao = (receita_venda_ativo + receita_liquida_call_pre_ir + receita_venda_put_residual) - (custo_base_ajustado + taxa_saida_b3 + corretagem_saida)
ir_devido_operacao = max(0.0, lucro_bruto_operacao * ir_opcoes)
lucro_liquido_final = lucro_bruto_operacao - ir_devido_operacao

rentabilidade_sobre_capital_inicial = (lucro_liquido_final / custo_base_bruto) * 100 if custo_base_bruto > 0 else 0.0

if "Simples" in tipo_juros:
    meta_acumulada_mes = meta_mensal * st.session_state['mes_operacao']
else:
    meta_acumulada_mes = (((1 + juros_liquido_am) ** st.session_state['mes_operacao']) - 1) * 100

st.markdown(f"#### Cenário Operacional Identificado: **{cenario_nome}**")

c_res1, c_res2, c_res3 = st.columns(3)
c_res1.metric("Lucro Líquido Final da Estrutura", f"R$ {lucro_liquido_final:,.2f}")
c_res2.metric("Retorno Total s/ Capital Inicial", f"{rentabilidade_sobre_capital_inicial:.2f}%")
c_res3.metric(f"Meta Selic Acumulada", f"{meta_acumulada_mes:.2f}%")

st.write("")

c_btn1, c_btn2 = st.columns(2)

with c_btn1:
    if st.button("➕ Fechar Mês: Rolar Call e Registrar Proventos", use_container_width=True):
        if qtd > 0:
            caixa_gerado_no_mes = receita_realmente_liquida_call + total_proventos_liquidos
            retorno_acum_capital_ini = ((st.session_state['caixa_acumulado_calls'] + st.session_state['caixa_proventos'] + caixa_gerado_no_mes) / custo_base_bruto) * 100
            
            novo_registro = {
                "Mês": st.session_state['mes_operacao'],
                "Call": ticker_call if ticker_call else "-",
                "Call Liq.": receita_realmente_liquida_call,
                "Proventos Liq.": total_proventos_liquidos,
                "Amort. Total": caixa_gerado_no_mes,
                "PM Ajustado": preco_medio_atual - (caixa_gerado_no_mes / qtd),
                "Retorno Acum.": retorno_acum_capital_ini
            }
            
            st.session_state['historico_rolagens'].append(novo_registro)
            st.session_state['caixa_acumulado_calls'] += receita_realmente_liquida_call
            st.session_state['caixa_proventos'] += total_proventos_liquidos
            st.session_state['mes_operacao'] += 1
            st.rerun()
        else:
            st.error("Preencha a Quantidade e Preço da Ação na Fase 1 primeiro.")

with c_btn2:
    if st.button("🛑 Zerar Histórico Atual", type="primary", use_container_width=True):
        zerar_dados_financeiros()
        st.rerun()

if st.session_state['historico_rolagens']:
    st.subheader("📊 Histórico Salvo (Lembre de clicar em Salvar na Nuvem no topo da página)")
    df_historico = pd.DataFrame(st.session_state['historico_rolagens'])
    
    cols_moeda = ["Call Liq.", "Proventos Liq.", "Amort. Total", "PM Ajustado"]
    for col in cols_moeda:
        df_historico[col] = df_historico[col].apply(lambda x: f"R$ {x:.2f}")
    df_historico["Retorno Acum."] = df_historico["Retorno Acum."].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(df_historico, use_container_width=True, hide_index=True)
