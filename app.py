import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO VISUAL E TRADUÇÃO
# ==========================================
st.set_page_config(page_title="Gouldian Invest | Quant", page_icon="🦅", layout="wide", initial_sidebar_state="expanded")

# CSS Customizado para um visual mais limpo e profissional
CUSTOM_CSS = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        border-radius: 4px 4px 0px 0px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    </style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

MESES_CURTOS = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
MESES_LONGOS = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception:
    st.error("🚨 Erro na conexão segura de dados. Verifique suas credenciais no Streamlit Secrets.")
    st.stop()

# ==========================================
# GERENCIAMENTO DE ESTADOS (ANTI-QUEBRA)
# ==========================================
def inicializar_estrategia_vazia():
    hoje = datetime.date.today()
    st.session_state['nome_estrategia_atual'] = ""
    st.session_state['historico_rolagens'] = []
    st.session_state['ciclo_nome'] = f"Série {MESES_CURTOS[hoje.month-1]}/{hoje.strftime('%y')}"
    st.session_state['val_preco_acao'] = None
    st.session_state['val_qtd'] = None
    st.session_state['val_ticker_put'] = ""
    st.session_state['val_preco_put'] = None
    st.session_state['val_strike_put'] = None
    st.session_state['val_ticker_call'] = ""
    st.session_state['val_strike_call'] = None
    st.session_state['val_premio_call'] = None
    st.session_state['val_dividendos'] = None
    st.session_state['val_jscp'] = None
    st.session_state['val_data_vencimento'] = hoje + datetime.timedelta(days=21)

def carregar_estrategia_salva(nome, pkg):
    st.session_state['nome_estrategia_atual'] = nome
    st.session_state['historico_rolagens'] = pkg.get('historico_rolagens', [])
    st.session_state['ciclo_nome'] = pkg.get('ciclo_nome', st.session_state.get('ciclo_nome', ""))
    st.session_state['val_preco_acao'] = pkg.get('preco_acao', None)
    st.session_state['val_qtd'] = pkg.get('qtd', None)
    st.session_state['val_ticker_put'] = pkg.get('ticker_put', "")
    st.session_state['val_preco_put'] = pkg.get('preco_put', None)
    st.session_state['val_strike_put'] = pkg.get('strike_put', None)
    st.session_state['val_ticker_call'] = pkg.get('ticker_call', "")
    st.session_state['val_strike_call'] = pkg.get('strike_call', None)
    st.session_state['val_premio_call'] = pkg.get('premio_call', None)
    st.session_state['val_dividendos'] = pkg.get('dividendos', None)
    st.session_state['val_jscp'] = pkg.get('jscp', None)
    st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

# ==========================================
# MOTORES INSTITUCIONAIS E AUTOMAÇÃO
# ==========================================
def buscar_dados_opcao_brapi(underlying, target_ticker):
    if not underlying or not target_ticker:
        st.warning("⚠️ Informe o Ticker da Ação (Barra Lateral) e o Ticker da Opção para buscar.")
        return None

    token = st.secrets.get("BRAPI_TOKEN", "")
    if not token:
        st.error("🚨 ERRO: BRAPI_TOKEN não encontrado.")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    underlying_clean = underlying.upper().replace(".SA", "")
    target_ticker_clean = target_ticker.upper()

    exp_url = f"https://brapi.dev/api/v2/options/expirations?underlying={underlying_clean}"
    try:
        with st.spinner(f"Consultando B3 para {target_ticker_clean}..."):
            resp_exp = requests.get(exp_url, headers=headers, timeout=10)
            if resp_exp.status_code != 200: return None
            vencimentos = resp_exp.json().get("expirations", [])
            
            for data_venc in vencimentos:
                chain_url = f"https://brapi.dev/api/v2/options/chain?underlying={underlying_clean}&expirationDate={data_venc}"
                resp_chain = requests.get(chain_url, headers=headers, timeout=10)
                
                if resp_chain.status_code == 200:
                    series = resp_chain.json().get("series", [])
                    opcao = next((item for item in series if item["symbol"] == target_ticker_clean), None)
                    
                    if opcao:
                        return {
                            "preco": float(opcao.get("close", 0.0)),
                            "strike": float(opcao.get("strike", 0.0)),
                            "vencimento": datetime.datetime.strptime(data_venc, "%Y-%m-%d").date()
                        }
        st.warning(f"⚠️ Ticker '{target_ticker_clean}' não encontrado nos vencimentos ativos.")
        return None
    except requests.exceptions.RequestException:
        return None

@st.cache_data(ttl=300)
def buscar_sugestoes_calls_cached(underlying, strike_minimo):
    if not underlying or strike_minimo <= 0: return []
    token = st.secrets.get("BRAPI_TOKEN", "")
    if not token: return []
    
    headers = {"Authorization": f"Bearer {token}"}
    underlying_clean = underlying.upper().replace(".SA", "")
    
    def is_terceira_sexta(date_str):
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        return d.weekday() == 4 and 15 <= d.day <= 21

    try:
        exp_url = f"https://brapi.dev/api/v2/options/expirations?underlying={underlying_clean}"
        resp_exp = requests.get(exp_url, headers=headers, timeout=5)
        if resp_exp.status_code != 200: return []
        
        vencimentos = resp_exp.json().get("expirations", [])
        venc_validos = [v for v in vencimentos if datetime.datetime.strptime(v, "%Y-%m-%d").date() > datetime.date.today() and is_terceira_sexta(v)]
        if not venc_validos: return []
        
        data_venc = venc_validos[0] 
        chain_url = f"https://brapi.dev/api/v2/options/chain?underlying={underlying_clean}&expirationDate={data_venc}"
        resp_chain = requests.get(chain_url, headers=headers, timeout=5)
        if resp_chain.status_code != 200: return []
        
        series = resp_chain.json().get("series", [])
        calls = []
        for item in series:
            sym = item.get("symbol", "")
            is_call = len(sym) >= 5 and sym[4].upper() in "ABCDEFGHIJKL"
            
            if is_call:
                strike = float(item.get("strike", 0.0))
                if strike >= strike_minimo:
                    preco = float(item.get("close", 0.0))
                    if preco > 0: 
                        calls.append({
                            "Ticker": sym,
                            "Strike (R$)": strike,
                            "Prêmio (R$)": preco,
                            "Vencimento": data_venc
                        })
        
        calls.sort(key=lambda x: x["Strike (R$)"])
        return calls[:5]
    except Exception:
        return []

# ==========================================
# 1. CONTROLE DE AMBIENTE E SUPABASE AUTH
# ==========================================
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False
if 'username' not in st.session_state: st.session_state['username'] = ""
if 'preco_acao_tela' not in st.session_state: st.session_state['preco_acao_tela'] = 0.0

if "access_token" in st.query_params and not st.session_state['logged_in']:
    token_jwt = st.query_params["access_token"]
    try:
        user_auth = supabase.auth.get_user(token_jwt)
        if user_auth and user_auth.user:
            email_logado = user_auth.user.email
            st.session_state['logged_in'] = True
            st.session_state['username'] = email_logado.split('@')[0].capitalize()
            st.session_state['user_email_completo'] = email_logado

            db_res = supabase.table("usuarios").select("*").eq("email", email_logado).execute()
            if len(db_res.data) > 0:
                st.session_state['dados_nuvem'] = db_res.data[0].get("dados", {"estrategias": {}})
            else:
                st.session_state['dados_nuvem'] = {"estrategias": {}}

            st.session_state['projeto_index'] = 0
            inicializar_estrategia_vazia()
    except:
        pass

if not st.session_state['logged_in']:
    # TELA DE LOGIN ESTILIZADA
    st.markdown("<br><br>", unsafe_allow_html=True)
    col_spacer1, col_login_main, col_spacer2 = st.columns([1, 2, 1])
    
    with col_login_main:
        st.markdown("<h1 style='text-align: center;'>🦅 Gouldian Invest</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Plataforma Quantitativa de Engenharia Financeira de Derivativos</p>", unsafe_allow_html=True)
        
        with st.container(border=True):
            modo = st.pills("Acesso", ["Entrar", "Criar Conta"], default="Entrar")
            st.divider()

            email_input = st.text_input("E-mail corporativo ou pessoal", placeholder="seu@email.com").strip().lower()
            senha_input = st.text_input("Senha", type="password", placeholder="••••••••")

            if modo == "Entrar":
                if st.button("Acessar Plataforma", type="primary", use_container_width=True):
                    if email_input and senha_input:
                        try:
                            auth_response = supabase.auth.sign_in_with_password({"email": email_input, "password": senha_input})
                            st.session_state['logged_in'] = True
                            st.session_state['username'] = email_input.split('@')[0].capitalize()
                            st.session_state['user_email_completo'] = email_input
                            st.query_params["access_token"] = auth_response.session.access_token

                            db_res = supabase.table("usuarios").select("*").eq("email", email_input).execute()
                            if len(db_res.data) > 0:
                                st.session_state['dados_nuvem'] = db_res.data[0].get("dados", {"estrategias": {}})
                            else:
                                st.session_state['dados_nuvem'] = {"estrategias": {}}
                                supabase.table("usuarios").insert({"email": email_input, "dados": st.session_state['dados_nuvem']}).execute()

                            st.session_state['projeto_index'] = 0
                            inicializar_estrategia_vazia()
                            st.rerun()
                        except Exception:
                            st.error("Credenciais inválidas. Tente novamente.")
                    else:
                        st.warning("Preencha todos os campos.")

            elif modo == "Criar Conta":
                if st.button("Registrar e Acessar", type="primary", use_container_width=True):
                    if email_input and senha_input:
                        try:
                            auth_response = supabase.auth.sign_up({"email": email_input, "password": senha_input})
                            if auth_response.session:
                                st.session_state['logged_in'] = True
                                st.session_state['username'] = email_input.split('@')[0].capitalize()
                                st.session_state['user_email_completo'] = email_input
                                st.query_params["access_token"] = auth_response.session.access_token
                                st.session_state['dados_nuvem'] = {"estrategias": {}}
                                supabase.table("usuarios").insert({"email": email_input, "dados": st.session_state['dados_nuvem']}).execute()
                                st.success("Conta criada com sucesso!")
                                st.rerun()
                        except Exception:
                            st.error("Falha no cadastro (a senha deve ter no mínimo 6 caracteres).")
    st.stop()

# ==========================================
# 2. MENU LATERAL (GLOBAL SETTINGS & DATA)
# ==========================================
with st.sidebar:
    st.markdown("## 🦅 Gouldian Invest")
    st.caption(f"Logado como: **{st.session_state['username']}**")
    if st.button("Sair (Logout) 🚪", use_container_width=True):
        supabase.auth.sign_out()
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()
    
    st.divider()
    
    st.markdown("### 🔍 Monitor de Mercado")
    ticker_acao = st.text_input("Ticker do Ativo Base", value="", placeholder="Ex: PETR4.SA, BOVA11.SA", help="Insira o ticker com o sufixo .SA para buscar a cotação no Yahoo Finance.")
    
    col_btn_b3, col_preco_b3 = st.columns([1, 1])
    with col_btn_b3:
        if st.button("Cotação", use_container_width=True):
            if ticker_acao:
                try:
                    with st.spinner("Buscando..."):
                        acao = yf.Ticker(ticker_acao)
                        preco_atual = acao.history(period="1d")['Close'].iloc[-1]
                        st.session_state['preco_acao_tela'] = float(preco_atual)
                        st.rerun()
                except:
                    st.error("Ativo indisponível.")
    with col_preco_b3:
        st.markdown(f"<h3 style='margin-top: 0px; text-align: right; color: #4CAF50;'>R$ {st.session_state['preco_acao_tela']:.2f}</h3>", unsafe_allow_html=True)

    st.divider()

    with st.expander("⚙️ Custos e Corretagem", expanded=False):
        corretagem = st.number_input("Corretagem Fixa (R$)", value=0.00, step=1.0, help="Custo por ordem executada na sua corretora.")
        emol_acao = st.number_input("Emolumentos Ação (%)", value=0.0325, format="%.4f") / 100
        emol_opcao = st.number_input("Emolumentos Opção (%)", value=0.0375, format="%.4f") / 100
        taxa_ex_b3 = st.number_input("Taxa Exercício B3 (%)", value=0.5, step=0.1, help="Taxa cobrada pela B3 em caso de exercício da opção.") / 100

    with st.expander("🏛️ Tributação e Juros", expanded=False):
        ir_opcoes = st.number_input("IR Opções (%)", value=15.0, step=0.5, help="Imposto de renda sobre o lucro líquido da operação estruturada.") / 100
        ir_jscp_tax = st.number_input("IR JSCP (%)", value=15.0, step=0.5) / 100
        juros_bruto_aa = st.number_input("Taxa Selic Bruta (% a.a.)", value=14.50, step=0.1, help="Taxa livre de risco usada como benchmark de custo de oportunidade.") / 100
        ir_renda_fixa = st.number_input("IR Renda Fixa (%)", value=22.5, step=0.5) / 100
        juros_liquido_aa = juros_bruto_aa * (1 - ir_renda_fixa)

# ==========================================
# 3. CABEÇALHO DO PROJETO E SELETOR
# ==========================================
dict_estrategias = st.session_state['dados_nuvem'].get("estrategias", {})
opcoes_projeto = ["✨ -- Criar Nova Estratégia do Zero --"] + list(dict_estrategias.keys())

if 'projeto_index' not in st.session_state: st.session_state['projeto_index'] = 0

col_proj_sel, col_proj_blank = st.columns([1, 2])
with col_proj_sel:
    projeto_escolhido = st.selectbox("📂 Selecione o Projeto/Estratégia:", opcoes_projeto, index=st.session_state['projeto_index'])

if 'ultimo_projeto_escolhido' not in st.session_state or st.session_state['ultimo_projeto_escolhido'] != projeto_escolhido:
    st.session_state['ultimo_projeto_escolhido'] = projeto_escolhido
    st.session_state['projeto_index'] = opcoes_projeto.index(projeto_escolhido)
    if projeto_escolhido == "✨ -- Criar Nova Estratégia do Zero --":
        inicializar_estrategia_vazia()
    else:
        carregar_estrategia_salva(projeto_escolhido, dict_estrategias[projeto_escolhido])
    st.rerun()

# RECALCULO DINÂMICO DOS ACUMULADOS (Rodando sempre para refletir em todas as abas)
caixa_acumulado_calls = sum(float(linha.get("Renda Opção Liq.", 0.0)) for linha in st.session_state['historico_rolagens'])
caixa_proventos = sum(float(linha.get("Dividendos/JSCP Liq.", 0.0)) for linha in st.session_state['historico_rolagens'])
caixa_total_gerado = caixa_acumulado_calls + caixa_proventos

# ==========================================
# 4. NÚCLEO DA APLICAÇÃO (TABS)
# ==========================================
tab_estrutura, tab_rolagem, tab_simulador, tab_historico = st.tabs([
    "1️⃣ Montagem (Ação + Put)", 
    "2️⃣ Amortização (Call + Proventos)", 
    "3️⃣ Simulador de Payoff", 
    "4️⃣ Banco de Dados"
])

# ------------------------------------------
# ABA 1: ESTRUTURA BASE
# ------------------------------------------
with tab_estrutura:
    st.markdown("### Configuração do Ativo e Proteção (Seguro de Carteira)")
    st.caption("Defina o ativo subjacente que você possui e a Put comprada para travamento de risco de cauda.")
    
    col_acao, col_put = st.columns(2)
    
    with col_acao:
        with st.container(border=True):
            st.markdown("#### 🏢 1. Ativo Base (Ação/ETF)")
            
            valor_default_acao = st.session_state['val_preco_acao'] if st.session_state['val_preco_acao'] else (st.session_state['preco_acao_tela'] if st.session_state['preco_acao_tela'] > 0 else None)
            
            preco_acao_raw = st.number_input("Preço Médio de Aquisição (R$)", value=valor_default_acao, placeholder="0.00", format="%.2f", help="O valor pelo qual você comprou o ativo ou o preço de fechamento atual para simulação.")
            qtd_raw = st.number_input("Quantidade Exposta", value=st.session_state['val_qtd'], placeholder="Ex: 1000", step=100, help="Quantidade total do ativo subjacente. Lotes padrão geralmente são múltiplos de 100.")
            
            preco_acao = preco_acao_raw if preco_acao_raw is not None else 0.0
            qtd = int(qtd_raw) if qtd_raw is not None else 0
            
            st.session_state['val_preco_acao'] = preco_acao
            st.session_state['val_qtd'] = qtd

    with col_put:
        with st.container(border=True):
            st.markdown("#### 🛡️ 2. Seguro Longo (Long Put)")
            
            c_put_tick, c_put_btn = st.columns([3, 1])
            with c_put_tick:
                ticker_put = st.text_input("Ticker da Put", value=st.session_state['val_ticker_put'], placeholder="Ex: PETRR454", help="Insira o ticker da opção de venda (Put) que servirá como piso de proteção da sua carteira.")
                st.session_state['val_ticker_put'] = ticker_put
            with c_put_btn:
                st.write("") # Espaçamento para alinhar com o input
                if st.button("Buscar API", key="btn_put", use_container_width=True):
                    dados_api = buscar_dados_opcao_brapi(ticker_acao, ticker_put)
                    if dados_api:
                        st.session_state['val_preco_put'] = dados_api['preco']
                        if dados_api['strike'] > 0: st.session_state['val_strike_put'] = dados_api['strike']
                        st.toast(f"✅ Dados de {ticker_put} carregados com sucesso!")
                        st.rerun()

            c_put_price, c_put_strike = st.columns(2)
            with c_put_price:
                preco_put_raw = st.number_input("Prêmio Pago na Put (R$)", value=st.session_state['val_preco_put'], placeholder="0.00", format="%.2f", help="Custo unitário da opção de proteção.")
            with c_put_strike:
                strike_put_raw = st.number_input("Strike da Put (R$)", value=st.session_state['val_strike_put'], placeholder="0.00", format="%.2f", help="Preço de exercício. Este será o preço mínimo garantido de venda da sua ação caso o mercado caia agressivamente.")

            st.session_state['val_preco_put'] = preco_put_raw
            st.session_state['val_strike_put'] = strike_put_raw

            preco_put = preco_put_raw if preco_put_raw is not None else 0.0
            strike_put = strike_put_raw if strike_put_raw is not None else 0.0

    # Cálculos da Aba 1
    volume_acao = volume_put = tx_b3_entrada_acao = tx_b3_entrada_put = taxas_iniciais_totais = 0.0
    custo_base_bruto = custo_base_ajustado = strike_minimo = 0.0

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
    
    st.markdown("#### 📊 Resumo de Risco e Imobilização")
    with st.container(border=True):
        col_res1, col_res2, col_res3 = st.columns(3)
        col_res1.metric(label="Capital Inicial Imobilizado", value=f"R$ {custo_base_bruto:,.2f}", help="Custo total (Ação + Put + Taxas Iniciais).")
        col_res2.metric(label="Custo Linha Ajustado (PM)", value=f"R$ {custo_base_ajustado:,.2f}", delta=f"Proventos: R$ {caixa_total_gerado:,.2f}", delta_color="inverse", help="Capital inicial abatido de todo o caixa gerado em lançamentos passados.")
        col_res3.metric(label="🎯 Strike Mín. de Segurança", value=f"R$ {strike_minimo:.2f}", help="Se você vender Calls com strike ABAIXO deste valor, assumirá prejuízo garantido no caso de exercício.")

# ------------------------------------------
# ABA 2: ROLAGEM E AMORTIZAÇÃO
# ------------------------------------------
with tab_rolagem:
    st.markdown("### Lançamentos de Opcões e Recebimento de Proventos")
    st.caption("Lance Calls (Venda Coberta) para gerar renda e reduzir o Preço Médio (Amortização do Collar).")
    
    col_cron1, col_cron2 = st.columns(2)
    with col_cron1:
        ciclo_nome_input = st.text_input("🔖 Identificador do Ciclo", value=st.session_state['ciclo_nome'], help="Nome para identificar esta rolagem no histórico (Ex: Série D).")
        st.session_state['ciclo_nome'] = ciclo_nome_input
    with col_cron2:
        data_montagem = st.date_input("🗓️ Data Base (Início/Rolagem)", value=datetime.date.today(), format="DD/MM/YYYY")

    sub_tab_call, sub_tab_proventos = st.tabs(["🔄 Lançamento de Call (Venda Coberta)", "💰 Proventos Recebidos"])

    with sub_tab_call:
        if strike_minimo > 0 and ticker_acao:
            sugestoes = buscar_sugestoes_calls_cached(ticker_acao, strike_minimo)
            if sugestoes:
                melhor_call = sugestoes[0]
                if not st.session_state['val_ticker_call']:
                    st.session_state['val_ticker_call'] = melhor_call['Ticker']
                    st.session_state['val_strike_call'] = melhor_call['Strike (R$)']
                    st.session_state['val_premio_call'] = melhor_call['Prêmio (R$)']
                    st.session_state['val_data_vencimento'] = datetime.datetime.strptime(melhor_call['Vencimento'], "%Y-%m-%d").date()
                    st.rerun()

                st.success(f"🤖 **Radar Quantitativo:** A Call mensal (3ª Sexta-Feira) sugerida acima do Break-Even é **{melhor_call['Ticker']}** (Strike R$ {melhor_call['Strike (R$)']:.2f} | R$ {melhor_call['Prêmio (R$)']:.2f}).")
            else:
                st.info("Aguardando ativos líquidos de vencimento mensal acima do ponto de equilíbrio calculados na Aba 1.")

        with st.container(border=True):
            col_input_call, col_metric_call = st.columns([1, 1.2])
            
            with col_input_call:
                c_call_tick, c_call_btn = st.columns([3, 1])
                with c_call_tick:
                    ticker_call = st.text_input("Ticker da Call Lançada", value=st.session_state['val_ticker_call'])
                    st.session_state['val_ticker_call'] = ticker_call
                with c_call_btn:
                    st.write("")
                    if st.button("Sinc.", key="btn_call", use_container_width=True, help="Buscar cotação na Brapi"):
                        dados_api = buscar_dados_opcao_brapi(ticker_acao, ticker_call)
                        if dados_api:
                            st.session_state['val_premio_call'] = dados_api['preco']
                            if dados_api['strike'] > 0: st.session_state['val_strike_call'] = dados_api['strike']
                            if dados_api['vencimento']: st.session_state['val_data_vencimento'] = dados_api['vencimento']
                            st.toast("✅ Call sincronizada!")
                            st.rerun()

                data_vencimento = st.date_input("🗓️ Data de Vencimento da Call", value=st.session_state['val_data_vencimento'], format="DD/MM/YYYY")
                st.session_state['val_data_vencimento'] = data_vencimento

                strike_call_raw = st.number_input("Strike da Call (R$)", value=st.session_state['val_strike_call'], placeholder="0.00", format="%.2f")
                premio_call_raw = st.number_input("Prêmio Recebido (R$)", value=st.session_state['val_premio_call'], placeholder="0.00", format="%.2f", help="O valor que você recebe na conta ao vender a Opção de Compra.")

                st.session_state['val_strike_call'] = strike_call_raw
                st.session_state['val_premio_call'] = premio_call_raw

                strike_call = strike_call_raw if strike_call_raw is not None else 0.0
                premio_call = premio_call_raw if premio_call_raw is not None else 0.0

            with col_metric_call:
                dias_uteis = max(1, len(pd.bdate_range(data_montagem, data_vencimento)))
                meta_ciclo_perc = (((1 + juros_liquido_aa) ** (dias_uteis / 252)) - 1) * 100
                meta_mes_cheio_perc = (((1 + juros_liquido_aa) ** (21 / 252)) - 1) * 100

                volume_call = premio_call * qtd
                custos_atrito_call = (volume_call * emol_opcao) + (corretagem if corretagem > 0 else 0.0)
                receita_liquida_call_pre_ir = volume_call - custos_atrito_call
                ir_isolado_call_po = receita_liquida_call_pre_ir * ir_opcoes
                receita_realmente_liquida_call = receita_liquida_call_pre_ir - ir_isolado_call_po

                st.markdown("#### Retorno Projetado do Ciclo")
                c_ret1, c_ret2 = st.columns(2)
                c_ret1.metric("Crédito D+1 Bruto", f"R$ {receita_liquida_call_pre_ir:,.2f}", help="Valor creditado descontando emolumentos e corretagem.")
                c_ret2.metric("Crédito Pós-IR (Líquido)", f"R$ {receita_realmente_liquida_call:,.2f}", help="Valor final livre, após a futura dedução via DARF.")

                data_darf = data_vencimento.replace(day=1) + datetime.timedelta(days=31)
                st.caption(f"🧾 **Provisão DARF:** R$ {ir_isolado_call_po:,.2f} (Pagamento: {MESES_LONGOS[data_darf.month-1]} de {data_darf.year})")

                if premio_call > 0 and custo_base_bruto > 0:
                    rendimento_call_ciclo = (receita_realmente_liquida_call / custo_base_bruto) * 100
                    st.divider()
                    if rendimento_call_ciclo < meta_ciclo_perc:
                        st.warning(f"⚠️ Prêmio Líquido (**{rendimento_call_ciclo:.2f}%**) é MENOR que a Selic do período (**{meta_ciclo_perc:.2f}%**).")
                    else:
                        st.success(f"🚀 Prêmio Líquido (**{rendimento_call_ciclo:.2f}%**) SUPERA a Selic do período (**{meta_ciclo_perc:.2f}%**).")

                if 0 < strike_call < strike_minimo:
                    st.error("🚨 Atenção: O Strike da Call está configurado ABAIXO do seu PM Ajustado (Strike Mínimo). Se exercido, causará prejuízo na operação completa.")

    with sub_tab_proventos:
        with st.container(border=True):
            st.markdown("Registre dividendos ou Juros sobre Capital Próprio (JSCP) anunciados no ciclo.")
            c_prov1, c_prov2, c_prov3 = st.columns(3)
            
            with c_prov1:
                div_brutos_raw = st.number_input("Dividendos (Isentos R$)", value=st.session_state['val_dividendos'], placeholder="0.00", format="%.2f")
                dividendos_brutos = div_brutos_raw if div_brutos_raw is not None else 0.0
            with c_prov2:
                jscp_brutos_raw = st.number_input("JSCP Bruto Declarado (R$)", value=st.session_state['val_jscp'], placeholder="0.00", format="%.2f")
                jscp_bruto = jscp_brutos_raw if jscp_brutos_raw is not None else 0.0

            ir_jscp = jscp_bruto * ir_jscp_tax
            total_proventos_liquidos = dividendos_brutos + (jscp_bruto - ir_jscp)

            with c_prov3:
                st.metric("Caixa Líquido Apropriado", f"R$ {total_proventos_liquidos:.2f}", f"Retenção JSCP: -R$ {ir_jscp:.2f}", delta_color="inverse")

# ------------------------------------------
# ABA 3: SIMULADOR DE DESFECHO
# ------------------------------------------
with tab_simulador:
    st.markdown("### 🔮 Stress Test e Simulador de Payoff")
    st.caption("Arraste o slider para simular o comportamento da sua estrutura baseada no preço da ação no dia do vencimento.")
    
    with st.container(border=True):
        max_slider = float(preco_acao * 2.0) if preco_acao > 0 else 100.0
        preco_vencimento = st.slider(
            "Preço do Ativo no Dia do Vencimento (R$)",
            min_value=0.0, max_value=max_slider,
            value=float(preco_acao if preco_acao > 0 else 10.0), step=0.10
        )

        valor_residual_put = 0.0
        deseja_exercer_put = False

        if preco_vencimento <= strike_put and strike_put > 0:
            st.info("📉 O mercado caiu! Sua proteção (Put) foi ativada. Você pode exercê-la (vender a ação pelo Strike) ou vendê-la na tela.")
            deseja_exercer_put = st.toggle("🛑 Quero EXERCER minha Put (Vender a ação pelo preço garantido).", value=True)
            if not deseja_exercer_put:
                valor_residual_put_raw = st.number_input("Valor de revenda da Put em tela (R$)", value=0.0, format="%.2f")
                valor_residual_put = valor_residual_put_raw if valor_residual_put_raw is not None else 0.0
        elif preco_vencimento > strike_put and strike_put > 0:
            st.caption("A Put virou 'pó'. Perdeu seu valor pois o mercado subiu ou ficou estável.")

        receita_venda_put_residual = valor_residual_put * qtd
        receita_venda_ativo = taxa_saida_b3 = corretagem_saida = 0.0
        cenario_nome = "Aguardando preenchimento da Estrutura Base (Aba 1)"
        cor_cenario = "normal"

        if qtd > 0:
            if preco_vencimento >= strike_call and strike_call > 0:
                cenario_nome = "🚀 EXERCÍCIO DA CALL (Lucro Máximo Atingido)"
                cor_cenario = "inverse"
                receita_venda_ativo = strike_call * qtd
                taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3
                corretagem_saida = corretagem if corretagem > 0 else 0.0
                receita_venda_put_residual = 0.0
            elif deseja_exercer_put:
                cenario_nome = "🛡️ EXECUÇÃO DA PUT (Seguro de Baixa Acionado)"
                receita_venda_ativo = strike_put * qtd
                taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3
                corretagem_saida = corretagem if corretagem > 0 else 0.0
                receita_venda_put_residual = 0.0
            else:
                cenario_nome = "⚖️ MANUTENÇÃO (Ativo Continua na Carteira)"
                receita_venda_ativo = preco_vencimento * qtd
                taxa_saida_b3 = receita_venda_ativo * emol_acao
                corretagem_saida = corretagem if corretagem > 0 else 0.0

        lucro_bruto_operacao = (receita_venda_ativo + receita_liquida_call_pre_ir + receita_venda_put_residual) - (custo_base_ajustado + taxa_saida_b3 + corretagem_saida)
        ir_devido_operacao = max(0.0, lucro_bruto_operacao * ir_opcoes)
        lucro_liquido_final = lucro_bruto_operacao - ir_devido_operacao
        rentabilidade_sobre_capital_inicial = (lucro_liquido_final / custo_base_bruto) * 100 if custo_base_bruto > 0 else 0.0

        mult_projetado = 1.0
        for linha in st.session_state['historico_rolagens']:
            meta_hist = linha.get('_Selic Ciclo', 0.0)
            mult_projetado *= (1 + (meta_hist / 100))
        if 'meta_ciclo_perc' in locals() and 'meta_ciclo_perc' not in [0.0]:
            mult_projetado *= (1 + (meta_ciclo_perc / 100))
        meta_acumulada_projetada = (mult_projetado - 1) * 100

        st.markdown(f"#### Status de Saída: **{cenario_nome}**")

        c_res1, c_res2, c_res3 = st.columns(3)
        c_res1.metric("L&P Líquido Estimado", f"R$ {lucro_liquido_final:,.2f}", help="Lucro ou Prejuízo financeiro total da operação.")
        c_res2.metric("Retorno Global (YOC)", f"{rentabilidade_sobre_capital_inicial:.2f}%", help="Rentabilidade em relação ao capital total inicialmente investido.")
        c_res3.metric("Benchmark Selic Acumulada", f"{meta_acumulada_projetada:.2f}%", delta=f"{rentabilidade_sobre_capital_inicial - meta_acumulada_projetada:.2f}% Alpha", help="O que a Selic rendeu (ou renderá) durante todo este período.")

# ------------------------------------------
# ABA 4: BANCO DE DADOS E HISTÓRICO
# ------------------------------------------
with tab_historico:
    st.markdown("### Arquivamento e Gestão de Portfólio")
    st.caption("Sempre que finalizar um lançamento (Aba 2), clique em 'Registrar Ciclo' para criar o histórico matemático da sua estratégia. Depois, salve o projeto inteiro na nuvem.")
    
    with st.container(border=True):
        c_btn1, c_btn2 = st.columns(2)
        
        with c_btn1:
            if st.button("➕ Registrar Ciclo e Rolar Estratégia", use_container_width=True, type="primary"):
                # Validação se as variáveis de Call foram inicializadas
                ticker_c = st.session_state.get('val_ticker_call', '')
                div_c = st.session_state.get('val_dividendos', None)
                jscp_c = st.session_state.get('val_jscp', None)

                if not ticker_c and not div_c and not jscp_c:
                    st.warning("Preencha os dados da Call lançada ou de Proventos (Aba 2) para registrar o ciclo.")
                else:
                    novo_ciclo = {
                        "Ciclo": st.session_state['ciclo_nome'],
                        "Vencimento": st.session_state['val_data_vencimento'].strftime("%d/%m/%Y"),
                        "Call Lançada": ticker_c if ticker_c else "-",
                        "Renda Opção Liq.": receita_realmente_liquida_call if ticker_c else 0.0,
                        "Dividendos/JSCP Liq.": total_proventos_liquidos if (div_c or jscp_c) else 0.0,
                        "_Selic Ciclo": meta_ciclo_perc if ticker_c else 0.0
                    }
                    
                    st.session_state['historico_rolagens'].append(novo_ciclo)
                    
                    # Limpa para a próxima rolagem
                    st.session_state['val_ticker_call'] = ""
                    st.session_state['val_strike_call'] = None
                    st.session_state['val_premio_call'] = None
                    st.session_state['val_dividendos'] = None
                    st.session_state['val_jscp'] = None
                    
                    st.success(f"✅ Ciclo '{st.session_state['ciclo_nome']}' arquivado! Histórico atualizado.")
                    st.rerun()

        with c_btn2:
            nome_salvar = st.text_input("Nome da Estratégia para Salvar na Nuvem", value=st.session_state.get('nome_estrategia_atual', ''), placeholder="Ex: PETR4 Collar Longo Prazo", label_visibility="collapsed")
            
            if st.button("💾 Salvar/Atualizar Projeto", use_container_width=True):
                if nome_salvar.strip() == "":
                    st.error("⚠️ Escreva um nome no campo acima para salvar a estratégia.")
                else:
                    pacote = {
                        "historico_rolagens": st.session_state['historico_rolagens'],
                        "ciclo_nome": st.session_state['ciclo_nome'],
                        "preco_acao": st.session_state['val_preco_acao'],
                        "qtd": st.session_state['val_qtd'],
                        "ticker_put": st.session_state['val_ticker_put'],
                        "preco_put": st.session_state['val_preco_put'],
                        "strike_put": st.session_state['val_strike_put'],
                        "ticker_call": st.session_state['val_ticker_call'],
                        "strike_call": st.session_state['val_strike_call'],
                        "premio_call": st.session_state['val_premio_call'],
                        "dividendos": st.session_state['val_dividendos'],
                        "jscp": st.session_state['val_jscp']
                    }
                    
                    st.session_state['dados_nuvem']['estrategias'][nome_salvar] = pacote
                    st.session_state['nome_estrategia_atual'] = nome_salvar
                    
                    try:
                        supabase.table("usuarios").update({
                            "dados": st.session_state['dados_nuvem']
                        }).eq("email", st.session_state['user_email_completo']).execute()
                        
                        st.success(f"🚀 Projeto '{nome_salvar}' salvo com sucesso!")
                    except Exception as e:
                        st.error(f"Erro ao salvar na nuvem: {e}")

    st.markdown("#### 📜 Ledger de Amortização (Histórico de Lançamentos)")
    
    if st.session_state['historico_rolagens']:
        df_historico = pd.DataFrame(st.session_state['historico_rolagens'])
        st.dataframe(
            df_historico, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Renda Opção Liq.": st.column_config.NumberColumn("Renda Opção (R$)", format="R$ %.2f"),
                "Dividendos/JSCP Liq.": st.column_config.NumberColumn("Proventos (R$)", format="R$ %.2f"),
                "_Selic Ciclo": st.column_config.NumberColumn("Meta Selic (%)", format="%.2f%%")
            }
        )
        
        if st.button("🗑️ Limpar Histórico de Rolagens", type="secondary"):
            st.session_state['historico_rolagens'] = []
            st.rerun()
    else:
        st.info("Nenhum ciclo concluído registrado até o momento. Realize a primeira rolagem na Aba 2 e arquive.")
