import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import requests
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO VISUAL COMPLETA (WHITE-LABEL)
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

REMOVER_BRANDING_CSS = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    </style>
"""
st.markdown(REMOVER_BRANDING_CSS, unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Erro na conexão segura de dados. Atualize a página.")
    st.stop()

# ==========================================
# FUNCTIONS DE GERENCIAMENTO DE ESTADOS (ANTI-QUEBRA)
# ==========================================
def inicializar_estrategia_vazia():
    st.session_state['nome_estrategia_atual'] = ""
    st.session_state['historico_rolagens'] = []
    st.session_state['ciclo_nome'] = f"Série {datetime.date.today().strftime('%b/%y')}"
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
    st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

def carregar_estrategia_salva(nome, pkg):
    st.session_state['nome_estrategia_atual'] = nome
    st.session_state['historico_rolagens'] = pkg.get('historico_rolagens', [])
    st.session_state['ciclo_nome'] = pkg.get('ciclo_nome', f"Série {datetime.date.today().strftime('%b/%y')}")
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

# --- MOTOR DE BUSCA INSTITUCIONAL (BRAPI) V2 CORRIGIDO ---
def buscar_dados_opcao_brapi(underlying, target_ticker):
    if not underlying or not target_ticker:
        st.warning("⚠️ Informe o Ticker da Ação (Barra Lateral) e o Ticker da Opção para buscar.")
        return None

    token = st.secrets.get("BRAPI_TOKEN", "")
    if not token:
        st.error("🚨 ERRO: O sistema não encontrou o BRAPI_TOKEN nos Secrets.")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    underlying_clean = underlying.upper().replace(".SA", "")
    target_ticker_clean = target_ticker.upper()

    exp_url = f"https://brapi.dev/api/v2/options/expirations?underlying={underlying_clean}"
    try:
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
        st.warning(f"⚠️ Ticker '{target_ticker_clean}' não encontrado nos vencimentos ativos de '{underlying_clean}'.")
        return None
    except requests.exceptions.RequestException:
        return None

@st.cache_data(ttl=300) # Cache de 5 min para não estourar limite da API
def buscar_sugestoes_calls_cached(underlying, strike_minimo):
    """Busca as Calls mais próximas e imediatamente superiores ao strike de segurança."""
    if not underlying or strike_minimo <= 0: return []
    
    token = st.secrets.get("BRAPI_TOKEN", "")
    if not token: return []
    
    headers = {"Authorization": f"Bearer {token}"}
    underlying_clean = underlying.upper().replace(".SA", "")
    
    try:
        exp_url = f"https://brapi.dev/api/v2/options/expirations?underlying={underlying_clean}"
        resp_exp = requests.get(exp_url, headers=headers, timeout=5)
        if resp_exp.status_code != 200: return []
        
        vencimentos = resp_exp.json().get("expirations", [])
        # Filtra vencimentos que já passaram para evitar distorções
        venc_validos = [v for v in vencimentos if datetime.datetime.strptime(v, "%Y-%m-%d").date() > datetime.date.today()]
        if not venc_validos: return []
        
        data_venc = venc_validos[0] # Pega o mais próximo
        chain_url = f"https://brapi.dev/api/v2/options/chain?underlying={underlying_clean}&expirationDate={data_venc}"
        resp_chain = requests.get(chain_url, headers=headers, timeout=5)
        if resp_chain.status_code != 200: return []
        
        series = resp_chain.json().get("series", [])
        calls = []
        for item in series:
            sym = item.get("symbol", "")
            # Pela regra B3, a 5ª letra indica o mês de vencimento da Call (A a L)
            is_call = len(sym) >= 5 and sym[4].upper() in "ABCDEFGHIJKL"
            
            if is_call:
                strike = float(item.get("strike", 0.0))
                # Filtra apenas strikes que não dão prejuízo no capital base
                if strike >= strike_minimo:
                    preco = float(item.get("close", 0.0))
                    if preco > 0: # Remove opções sem liquidez recente
                        calls.append({
                            "Ticker": sym,
                            "Strike (R$)": strike,
                            "Prêmio (R$)": preco,
                            "Vencimento": data_venc
                        })
        
        # Ordena pelo strike mais próximo do mínimo de segurança
        calls.sort(key=lambda x: x["Strike (R$)"])
        return calls[:5]
    except Exception:
        return []

# ==========================================
# 1. CONTROLE DE AMBIENTE E SUPABASE AUTH
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'preco_acao_tela' not in st.session_state:
    st.session_state['preco_acao_tela'] = 0.0

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
    with st.container():
        col_logo, col_titulo = st.columns([1, 8])
        with col_logo:
            st.title("🦅")
        with col_titulo:
            st.title("Gouldian Invest")
            st.markdown("Plataforma Quantitativa de Engenharia Financeira de Derivativos.")

    st.divider()

    col_login, col_vazia = st.columns([1, 2])
    with col_login:
        with st.container(border=True):
            st.subheader("Painel de Acesso")
            modo = st.radio("Selecione sua ação:", ["Login", "Criar Conta", "Esqueci a Senha"], horizontal=True)

            if modo in ["Login", "Criar Conta"]:
                email_input = st.text_input("E-mail corporativo ou pessoal").strip().lower()
                senha_input = st.text_input("Senha", type="password")

                if modo == "Login":
                    if st.button("Entrar na Plataforma", type="primary", use_container_width=True):
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
                                st.error("Erro de autenticação. Verifique suas credenciais.")
                        else:
                            st.warning("Preencha todos os campos para continuar.")

                elif modo == "Criar Conta":
                    if st.button("Concluir Cadastro e Entrar", type="primary", use_container_width=True):
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
                                    st.success("🎉 Conta criada com sucesso!")
                                    st.rerun()
                            except Exception as err:
                                st.error("Falha no cadastro (senha deve ter no mínimo 6 caracteres).")

            elif modo == "Esqueci a Senha":
                st.info("🔧 Módulo de recuperação por e-mail em configuração temporária. Acione o suporte caso precise resetar.")
    st.stop()

# ==========================================
# 2. SEÇÃO DE PERFIL E GERENCIAMENTO
# ==========================================
if 'val_data_vencimento' not in st.session_state:
    st.session_state['val_data_vencimento'] = datetime.date.today() + datetime.timedelta(days=21)

with st.container():
    c_header1, c_header2 = st.columns([8, 2])
    with c_header1:
        st.title("Gouldian Invest | Gestão de Collar Dinâmico")
        st.write(f"Sessão Ativa: **{st.session_state['username']}** | Conexão Segura e Criptografada 🛡️")
    with c_header2:
        st.write("")
        if st.button("Sair (Logout) 🚪", use_container_width=True):
            supabase.auth.sign_out()
            st.session_state['logged_in'] = False
            st.query_params.clear()
            st.rerun()

with st.expander("👤 Meu Perfil & Carteira de Estratégias", expanded=True):
    dict_estrategias = st.session_state['dados_nuvem'].get("estrategias", {})
    opcoes_projeto = ["-- Criar Nova Estratégia (Tela Limpa) --"] + list(dict_estrategias.keys())

    if 'projeto_index' not in st.session_state:
        st.session_state['projeto_index'] = 0

    projeto_escolhido = st.selectbox("📁 Selecione o Projeto / Estratégia em andamento:", opcoes_projeto, index=st.session_state['projeto_index'])

    if 'ultimo_projeto_escolhido' not in st.session_state or st.session_state['ultimo_projeto_escolhido'] != projeto_escolhido:
        st.session_state['ultimo_projeto_escolhido'] = projeto_escolhido
        st.session_state['projeto_index'] = opcoes_projeto.index(projeto_escolhido)
        if projeto_escolhido == "-- Criar Nova Estratégia (Tela Limpa) --":
            inicializar_estrategia_vazia()
        else:
            carregar_estrategia_salva(projeto_escolhido, dict_estrategias[projeto_escolhido])
        st.rerun()

st.divider()

# ==========================================
# RECALCULO DINÂMICO DOS ACUMULADOS
# ==========================================
caixa_acumulado_calls = 0.0
caixa_proventos = 0.0

if st.session_state['historico_rolagens']:
    for linha in st.session_state['historico_rolagens']:
        caixa_acumulado_calls += float(linha.get("Renda Opção Liq.", 0.0))
        caixa_proventos += float(linha.get("Dividendos/JSCP Liq.", 0.0))

caixa_total_gerado = caixa_acumulado_calls + caixa_proventos

# ==========================================
# 3. BARRA LATERAL (MONITOR E CUSTOS)
# ==========================================
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2942/2942259.png", width=50)
st.sidebar.header("🔍 Monitor de Cotação")
ticker_acao = st.sidebar.text_input("Ticker da Ação", value="", placeholder="Ex: PETR4.SA", help="Adicione .SA para ativos brasileiros")
st.sidebar.markdown(f"**Preço de Tela Atual:** R$ {st.session_state['preco_acao_tela']:.2f}")

if st.sidebar.button("Buscar Preço B3"):
    if ticker_acao:
        try:
            acao = yf.Ticker(ticker_acao)
            preco_atual = acao.history(period="1d")['Close'].iloc[-1]
            st.session_state['preco_acao_tela'] = float(preco_atual)
            st.rerun()
        except:
            st.sidebar.error("Ativo indisponível.")

st.sidebar.divider()
st.sidebar.markdown("### Parâmetros Base")

with st.sidebar.expander("⚙️ Custos Operacionais e IR", expanded=False):
    st.caption("Ajuste as taxas conforme sua corretora.")
    ir_opcoes = st.number_input("IR Opções (%)", value=15.0, step=0.5) / 100
    ir_jscp_tax = st.number_input("IR JSCP (%)", value=15.0, step=0.5) / 100
    emol_acao = st.number_input("Emol. Ação (%)", value=0.0325, format="%.4f") / 100
    emol_opcao = st.number_input("Emol. Opção (%)", value=0.0375, format="%.4f") / 100
    corretagem = st.number_input("Corretagem Fixa (R$)", value=0.00, step=1.0)
    taxa_ex_b3 = st.number_input("Taxa Exercício B3 (%)", value=0.5, step=0.1) / 100

with st.sidebar.expander("🏦 Benchmark e Juros", expanded=False):
    st.caption("Custo de oportunidade do capital.")
    juros_bruto_aa = st.number_input("Selic Bruta (% a.a.)", value=14.50, step=0.1) / 100
    ir_renda_fixa = st.number_input("IR Renda Fixa (%)", value=22.5, step=0.5) / 100
    juros_liquido_aa = juros_bruto_aa * (1 - ir_renda_fixa)

# ==========================================
# FASE 1: MONTAGEM DO MODELO E CRONOLOGIA
# ==========================================
st.header("📦 Fase 1: Estrutura Principal da Operação")
st.caption("Configure os parâmetros de entrada e o cronograma do ciclo atual.")

with st.container(border=True):
    col_cron1, col_cron2, col_vazio_cron = st.columns([2, 2, 4])
    with col_cron1:
        ciclo_nome_input = st.text_input("🔖 Identificador do Ciclo Atual", value=st.session_state['ciclo_nome'])
        st.session_state['ciclo_nome'] = ciclo_nome_input
    with col_cron2:
        data_montagem = st.date_input("🗓️ Data Base (Início/Rolagem)", value=datetime.date.today(), format="DD/MM/YYYY")

col1, col2, col3 = st.columns(3)

with col1:
    with st.container(border=True):
        st.subheader("🏢 1. Ativo Base (Ação)")
        preco_acao_raw = st.number_input("Preço de Aquisição (R$)", value=st.session_state['val_preco_acao'], placeholder="0.00", format="%.2f")
        qtd_raw = st.number_input("Quantidade Exposta", value=st.session_state['val_qtd'], placeholder="1000", step=100)

        preco_acao = preco_acao_raw if preco_acao_raw is not None else 0.0
        qtd = int(qtd_raw) if qtd_raw is not None else 0

with col2:
    with st.container(border=True):
        st.subheader("🛡️ 2. Seguro Longo (Put)")

        c_put_tick, c_put_btn = st.columns([2, 1])
        with c_put_tick:
            ticker_put = st.text_input("Ticker da Put", value=st.session_state['val_ticker_put'], placeholder="PETRR454")
            st.session_state['val_ticker_put'] = ticker_put
        with c_put_btn:
            st.write("")
            st.write("")
            if st.button("⚡ Buscar", key="btn_put", use_container_width=True):
                dados_api = buscar_dados_opcao_brapi(ticker_acao, ticker_put)
                if dados_api:
                    st.session_state['val_preco_put'] = dados_api['preco']
                    if dados_api['strike'] > 0:
                        st.session_state['val_strike_put'] = dados_api['strike']
                    st.toast("✅ Put carregada com sucesso!")
                    st.rerun()

        preco_put_raw = st.number_input("Prêmio Pago (R$)", value=st.session_state['val_preco_put'], placeholder="0.00", format="%.2f")
        strike_put_raw = st.number_input("Strike (R$)", value=st.session_state['val_strike_put'], placeholder="0.00", format="%.2f")

        st.session_state['val_preco_put'] = preco_put_raw
        st.session_state['val_strike_put'] = strike_put_raw

        preco_put = preco_put_raw if preco_put_raw is not None else 0.0
        strike_put = strike_put_raw if strike_put_raw is not None else 0.0

# --- Cálculos Base ---
volume_acao = volume_put = tx_b3_entrada_acao = tx_b3_entrada_put = taxas_iniciais_totais = 0.0
custo_base_bruto = custo_base_ajustado = strike_minimo = preco_medio_atual = 0.0

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

with col3:
    with st.container(border=True):
        st.subheader("📊 3. Resumo Patrimonial")
        st.metric("Capital Inicial Imobilizado", f"R$ {custo_base_bruto:,.2f}")
        st.metric("Custo Linha Ajustado (PM)", f"R$ {custo_base_ajustado:,.2f}", f"Desconto Proventos: R$ {caixa_total_gerado:,.2f}", delta_color="inverse")
        st.info(f"🎯 **Strike Call de Segurança:** R$ {strike_minimo:.2f}", icon="ℹ️")

st.divider()

# ==========================================
# FASE 2: REMUNERAÇÃO E CRONOLOGIA DE VENCIMENTO
# ==========================================
st.header("⚡ Fase 2: Amortização Mensal (Lançamentos)")

tab1, tab2 = st.tabs(["🔄 Lançamento de Call (Venda Coberta)", "💰 Proventos Recebidos (Ativo Base)"])

with tab1:
    with st.container(border=True):
        
        # Bloco de Sugestão Automática de Opções Seguras
        if strike_minimo > 0 and ticker_acao:
            st.markdown(f"**Referência de Risco:** Strike Mínimo Seguro R$ {strike_minimo:.2f}")
            sugestoes = buscar_sugestoes_calls_cached(ticker_acao, strike_minimo)
            if sugestoes:
                melhor_call = sugestoes[0]
                st.info(f"💡 **Sugestão Automática (Sem Risco de Exercício no PM):** A opção mais próxima é **{melhor_call['Ticker']}** (Strike R$ {melhor_call['Strike (R$)']:.2f} | R$ {melhor_call['Prêmio (R$)']:.2f})")
                
                with st.expander("🔎 Ver outras opções próximas e seguras (Expander)"):
                    st.dataframe(pd.DataFrame(sugestoes), use_container_width=True)
            else:
                st.caption("Aguardando ativos líquidos acima do ponto de equilíbrio na B3.")
        
        st.divider()

        col4, col5 = st.columns([1, 1.5])
        with col4:
            c_call_tick, c_call_btn = st.columns([2, 1])
            with c_call_tick:
                ticker_call = st.text_input("Ticker da Call Lançada", value=st.session_state['val_ticker_call'], placeholder="Ex: PETRF54")
                st.session_state['val_ticker_call'] = ticker_call
            with c_call_btn:
                st.write("")
                st.write("")
                if st.button("⚡ Buscar", key="btn_call", use_container_width=True):
                    dados_api = buscar_dados_opcao_brapi(ticker_acao, ticker_call)
                    if dados_api:
                        st.session_state['val_premio_call'] = dados_api['preco']
                        if dados_api['strike'] > 0:
                            st.session_state['val_strike_call'] = dados_api['strike']
                        if dados_api['vencimento']:
                            st.session_state['val_data_vencimento'] = dados_api['vencimento']
                        st.toast("✅ Call sincronizada!")
                        st.rerun()

            data_vencimento = st.date_input("🗓️ Data de Vencimento", value=st.session_state['val_data_vencimento'], format="DD/MM/YYYY")
            st.session_state['val_data_vencimento'] = data_vencimento

            strike_call_raw = st.number_input("Strike da Call (R$)", value=st.session_state['val_strike_call'], placeholder="0.00", format="%.2f")
            premio_call_raw = st.number_input("Prêmio Recebido (R$)", value=st.session_state['val_premio_call'], placeholder="0.00", format="%.2f")

            st.session_state['val_strike_call'] = strike_call_raw
            st.session_state['val_premio_call'] = premio_call_raw

            strike_call = strike_call_raw if strike_call_raw is not None else 0.0
            premio_call = premio_call_raw if premio_call_raw is not None else 0.0

        # Matemática dos Dias Úteis e Selic Mês Cheio
        dias_uteis = len(pd.bdate_range(data_montagem, data_vencimento))
        dias_uteis = max(1, dias_uteis)
        
        # Meta 1: O que a Selic rende APENAS nos dias em que o dinheiro ficou travado
        meta_ciclo_perc = (((1 + juros_liquido_aa) ** (dias_uteis / 252)) - 1) * 100
        
        # Meta 2: O que a Selic rende em um mês fiscal padrão fechado (21 dias úteis)
        meta_mes_cheio_perc = (((1 + juros_liquido_aa) ** (21 / 252)) - 1) * 100

        volume_call = premio_call * qtd
        custos_atrito_call = (volume_call * emol_opcao) + (corretagem if corretagem > 0 else 0.0)
        receita_liquida_call_pre_ir = volume_call - custos_atrito_call
        ir_isolado_call_po = receita_liquida_call_pre_ir * ir_opcoes
        receita_realmente_liquida_call = receita_liquida_call_pre_ir - ir_isolado_call_po

        with col5:
            st.markdown("### Retorno Imediato do Ciclo")
            c_ret1, c_ret2 = st.columns(2)
            c_ret1.metric("Crédito D+1 (Bruto Ajustado)", f"R$ {receita_liquida_call_pre_ir:,.2f}")
            c_ret2.metric("Crédito Efetivo (Pós-IR)", f"R$ {receita_realmente_liquida_call:,.2f}")

            mes_pagamento_darf = (data_vencimento.replace(day=1) + datetime.timedelta(days=31)).strftime('%B/%Y').capitalize()
            st.caption(f"🧾 **Provisão Tributária:** A DARF gerada neste ciclo é de **R$ {ir_isolado_call_po:,.2f}**, devida no último dia útil de **{mes_pagamento_darf}**.")

            if premio_call > 0 and custo_base_bruto > 0:
                rendimento_call_ciclo = (receita_realmente_liquida_call / custo_base_bruto) * 100
                st.write("")
                
                # Validação 1: Rentabilidade Proporcional
                if rendimento_call_ciclo < meta_ciclo_perc:
                    st.warning(f"⚠️ **Alerta de Custo de Oportunidade:** Prêmio líquido (**{rendimento_call_ciclo:.2f}%**) é menor que a Selic proporcional do ciclo (**{meta_ciclo_perc:.2f}%**).")
                else:
                    st.success(f"🎯 **Operação Eficiente (Proporcional):** Prêmio líquido (**{rendimento_call_ciclo:.2f}%**) superior à Selic proporcional do ciclo (**{meta_ciclo_perc:.2f}%**).")

                # Validação 2: Rentabilidade no Mês Cheio (Atenção ao Risco de Imobilização)
                if rendimento_call_ciclo < meta_mes_cheio_perc:
                    st.error(f"📉 **Atenção (Perda no Mês Cheio):** Apesar do ganho proporcional, este prêmio não cobre o rendimento da Selic equivalente a um mês integral (**{meta_mes_cheio_perc:.2f}%**). Avalie se o capital imobilizado compensa o spread.")
                else:
                    st.success(f"🚀 **Superávit Mensal:** Excelente! A operação superou não só os dias investidos, mas rendeu mais do que a Selic geraria em um mês cheio inteiro (**{meta_mes_cheio_perc:.2f}%**).")

            if strike_call > 0 and strike_call < strike_minimo:
                st.error("🚨 Atenção: O Strike da Call está configurado ABAIXO do ponto de equilíbrio, gerando risco de prejuízo no exercício compulsório.")

with tab2:
    with st.container(border=True):
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

st.divider()

# ==========================================
# FASE 3: SIMULADOR DE PAYOFF COMPLETO
# ==========================================
st.header("🔮 Fase 3: Simulador de Desfecho (Payoff)")
with st.container(border=True):
    max_slider = float(preco_acao * 2.0) if preco_acao > 0 else 100.0
    preco_vencimento = st.slider(
        "Preço em Tela do Ativo no Vencimento (R$)",
        min_value=0.0, max_value=max_slider,
        value=float(preco_acao if preco_acao > 0 else 10.0), step=0.10
    )

    if preco_vencimento > strike_put and strike_put > 0:
        valor_residual_put = 0.0
    else:
        st.write("")
        valor_residual_put_raw = st.number_input("Ação despencou. Qual o valor de revenda da Put na tela? (R$)", value=None, format="%.2f")
        valor_residual_put = valor_residual_put_raw if valor_residual_put_raw is not None else 0.0

    receita_venda_put_residual = valor_residual_put * qtd
    deseja_exercer_put = False

    if preco_vencimento <= strike_put and strike_put > 0:
        deseja_exercer_put = st.checkbox("🛑 Encerrar Linha: Quero usar meu direito e **VENDER** a ação pelo Strike da Put.")

    receita_venda_ativo = taxa_saida_b3 = corretagem_saida = 0.0
    cenario_nome = "Aguardando preenchimento da Fase 1"

    if qtd > 0:
        if preco_vencimento >= strike_call and strike_call > 0:
            cenario_nome = "🚀 EXERCÍCIO DA CALL (Venda Compulsória no Alvo Máximo)"
            receita_venda_ativo = strike_call * qtd
            taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3
            corretagem_saida = corretagem if corretagem > 0 else 0.0
            receita_venda_put_residual = 0.0
        elif deseja_exercer_put:
            cenario_nome = "🛡️ EXECUÇÃO DO SEGURO (Venda Garantida no Strike da Put)"
            receita_venda_ativo = strike_put * qtd
            taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3
            corretagem_saida = corretagem if corretagem > 0 else 0.0
            receita_venda_put_residual = 0.0
        else:
            cenario_nome = "⚖️ MANUTENÇÃO (Ativo na Carteira / Sem Venda Compulsória)"
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
    if 'meta_ciclo_perc' in locals():
        mult_projetado *= (1 + (meta_ciclo_perc / 100))
    meta_acumulada_projetada = (mult_projetado - 1) * 100

    st.markdown(f"#### Status do Desfecho: **{cenario_nome}**")

    with st.container(border=True):
        c_res1, c_res2, c_res3 = st.columns(3)
        c_res1.metric("L&P Líquido Estimado", f"R$ {lucro_liquido_final:,.2f}")
        c_res2.metric("Retorno Global (YOC)", f"{rentabilidade_sobre_capital_inicial:.2f}%")
        c_res3.metric("Benchmark Selic Acumulada", f"{meta_acumulada_projetada:.2f}%")

st.divider()

# ==========================================
# FASE 4: CONSOLIDAÇÃO E SALVAMENTO
# ==========================================
st.header("⏳ Fase 4: Arquivamento e Banco de Dados")

with st.container(border=True):
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("➕ Enviar Ciclo para o Histórico Auditável", use_container_width=True):
            if qtd > 0:
                novo_registro = {
                    "Série/Ciclo": st.session_state['ciclo_nome'],
                    "Call Ref.": ticker_call if ticker_call else "-",
                    "Renda Opção Liq.": float(receita_realmente_liquida_call),
                    "Dividendos/JSCP Liq.": float(total_proventos_liquidos),
                    "_Strike Call": float(strike_call),
                    "_Premio Bruto Call": float(volume_call),
                    "_Custos B3 e Corretagem Call": float(custos_atrito_call),
                    "_DARF Retido Call": float(ir_isolado_call_po),
                    "_Dividendos Isentos": float(dividendos_brutos),
                    "_JSCP Bruto": float(jscp_bruto),
                    "_IR JSCP": float(ir_jscp),
                    "_Data Montagem": data_montagem.strftime('%Y-%m-%d'),
                    "_Data Vencimento": data_vencimento.strftime('%Y-%m-%d'),
                    "_Selic Ciclo": float(meta_ciclo_perc)
                }
                st.session_state['historico_rolagens'].append(novo_registro)

                meses_nomes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
                prox_data = data_vencimento + datetime.timedelta(days=21)
                st.session_state['ciclo_nome'] = f"Série {meses_nomes[prox_data.month-1]}/{prox_data.strftime('%y')}"
                st.rerun()
            else:
                st.error("Preencha a quantidade do Ativo Base antes de salvar.")

    with c_btn2:
        if st.button("🛑 Limpar Inputs da Tela", type="secondary", use_container_width=True):
            inicializar_estrategia_vazia()
            st.rerun()

    st.write("")

    col_save1, col_save2 = st.columns([3, 1])
    with col_save1:
        nome_projeto_salvar = st.text_input("Dê um nome ao seu Projeto", value=st.session_state['nome_estrategia_atual'])
    with col_save2:
        st.write(""); st.write("")
        if st.button("💾 Gravar Projeto na Nuvem", type="primary", use_container_width=True):
            if not nome_projeto_salvar.strip():
                st.warning("⚠️ Forneça um nome para identificar a estratégia.")
            else:
                dados_estrategia_atual = {
                    "preco_acao": preco_acao if preco_acao > 0 else None,
                    "qtd": qtd if qtd > 0 else None,
                    "ticker_put": ticker_put,
                    "preco_put": preco_put if preco_put > 0 else None,
                    "strike_put": strike_put if strike_put > 0 else None,
                    "ticker_call": ticker_call,
                    "strike_call": strike_call if strike_call > 0 else None,
                    "premio_call": premio_call if premio_call > 0 else None,
                    "dividendos": dividendos_brutos if dividendos_brutos > 0 else None,
                    "jscp": jscp_bruto if jscp_bruto > 0 else None,
                    "historico_rolagens": st.session_state['historico_rolagens'],
                    "ciclo_nome": st.session_state['ciclo_nome']
                }

                st.session_state['dados_nuvem']["estrategias"][nome_projeto_salvar.strip()] = dados_estrategia_atual
                st.session_state['nome_estrategia_atual'] = nome_projeto_salvar.strip()

                try:
                    supabase.table("usuarios").update({"dados": st.session_state['dados_nuvem']}).eq("email", st.session_state['user_email_completo']).execute()
                    st.success(f"Projeto '{nome_projeto_salvar.strip()}' sincronizado com sucesso!")
                    st.session_state['projeto_index'] = list(st.session_state['dados_nuvem']["estrategias"].keys()).index(nome_projeto_salvar.strip()) + 1
                    st.rerun()
                except Exception as err:
                    st.error(f"Falha de sincronização: {err}")

# ==========================================
# 5. TABELA DE AUDITORIA INTERATIVA E EXTRATO
# ==========================================
if st.session_state['historico_rolagens']:
    st.divider()
    st.subheader("📑 Livro-Razão e Memória de Cálculo")
    
    with st.container(border=True):
        df_base = pd.DataFrame(st.session_state['historico_rolagens'])
        if "Competência" in df_base.columns and "Série/Ciclo" not in df_base.columns:
            df_base.rename(columns={"Competência": "Série/Ciclo"}, inplace=True)

        df_corrigido = st.data_editor(
            df_base, use_container_width=True, num_rows="dynamic",
            column_config={
                "Série/Ciclo": st.column_config.TextColumn("Identificador", required=True),
                "Call Ref.": st.column_config.TextColumn("Call Ref."),
                "Renda Opção Liq.": st.column_config.NumberColumn("Opções (Líquido)", format="R$ %.2f"),
                "Dividendos/JSCP Liq.": st.column_config.NumberColumn("Proventos (Líquido)", format="R$ %.2f"),
            }
        )

        if not df_corrigido.equals(df_base):
            st.session_state['historico_rolagens'] = df_corrigido.to_dict(orient="records")
            st.rerun()

        st.markdown("### 🧾 Drill-Down (Auditoria Fiscal do Ciclo)")
        meses_consolidados_lista = [r.get("Série/Ciclo", r.get("Competência", "-")) for r in st.session_state['historico_rolagens']]

        if meses_consolidados_lista:
            mes_extrato = st.selectbox("Selecione um ciclo:", meses_consolidados_lista)
            dados_mes = next((item for item in st.session_state['historico_rolagens'] if item.get("Série/Ciclo", item.get("Competência")) == mes_extrato), None)

            if dados_mes:
                c_ext1, c_ext2, c_ext3 = st.columns(3)
                with c_ext1:
                    st.markdown("**1. Operações (Derivativos)**")
                    st.write(f"Prêmio Bruto: R$ {dados_mes.get('_Premio Bruto Call', 0.0):,.2f}")
                    st.write(f"Emolumentos/Corret.: R$ -{dados_mes.get('_Custos B3 e Corretagem Call', 0.0):,.2f}")
                    st.write(f"DARF: R$ -{dados_mes.get('_DARF Retido Call', 0.0):,.2f}")
                    st.info(f"**Resultado:** R$ {dados_mes.get('Renda Opção Liq.', 0.0):,.2f}")

                with c_ext2:
                    st.markdown("**2. Proventos (Ações)**")
                    st.write(f"Div. Isentos: R$ {dados_mes.get('_Dividendos Isentos', 0.0):,.2f}")
                    st.write(f"JSCP Bruto Declarado: R$ {dados_mes.get('_JSCP Bruto', 0.0):,.2f}")
                    st.write(f"IRRF Fonte: R$ -{dados_mes.get('_IR JSCP', 0.0):,.2f}")
                    st.info(f"**Resultado:** R$ {dados_mes.get('Dividendos/JSCP Liq.', 0.0):,.2f}")

                with c_ext3:
                    st.markdown("**3. Caixa Total Deste Ciclo**")
                    caixa_bruto_total = dados_mes.get('_Premio Bruto Call', 0.0) + dados_mes.get('_Dividendos Isentos', 0.0) + dados_mes.get('_JSCP Bruto', 0.0)
                    total_retencoes = dados_mes.get('_Custos B3 e Corretagem Call', 0.0) + dados_mes.get('_DARF Retido Call', 0.0) + dados_mes.get('_IR JSCP', 0.0)
                    caixa_liquido_total = caixa_bruto_total - total_retencoes

                    st.write(f"Receitas Brutas: R$ {caixa_bruto_total:,.2f}")
                    st.write(f"Saídas: R$ -{total_retencoes:,.2f}")
                    st.success(f"**Depósito Limpo:** R$ {caixa_liquido_total:,.2f}")

# ==========================================
# 6. PAINEL COMPARATIVO DE PERFORMANCE
# ==========================================
st.divider()
st.subheader("🏆 Painel de Desempenho Institucional (Histórico)")

with st.container(border=True):
    @st.cache_data(ttl=3600)
    def buscar_indicadores_mercado():
        try:
            tickers = ["^BVSP", "USDBRL=X"]
            dados_mkt = yf.download(tickers, period="1mo")['Close']
            ret_ibov = ((dados_mkt["^BVSP"].iloc[-1] / dados_mkt["^BVSP"].iloc[0]) - 1) * 100
            ret_usd = ((dados_mkt["USDBRL=X"].iloc[-1] / dados_mkt["USDBRL=X"].iloc[0]) - 1) * 100
            return float(ret_ibov), float(ret_usd)
        except:
            return 0.0, 0.0

    perf_ibov, perf_usd = buscar_indicadores_mercado()
    retorno_caixa_puro = (caixa_total_gerado / custo_base_bruto) * 100 if custo_base_bruto > 0 else 0.0

    meses_consolidados = len(st.session_state['historico_rolagens'])
    mult_realizado = 1.0
    for linha in st.session_state['historico_rolagens']:
        meta_hist = linha.get('_Selic Ciclo', 0.0)
        if meta_hist == 0.0 and juros_liquido_aa > 0:
            meta_hist = (((1 + juros_liquido_aa) ** (21 / 252)) - 1) * 100
        mult_realizado *= (1 + (meta_hist / 100))

    meta_acumulada_realizada = (mult_realizado - 1) * 100
    alpha_gerado = retorno_caixa_puro - meta_acumulada_realizada
    darf_mes_atual = ir_isolado_call_po if 'ir_isolado_call_po' in locals() else 0.0

    c_perf1, c_perf2, c_perf3, c_perf4, c_perf5, c_perf6 = st.columns(6)

    c_perf1.metric("Caixa Absoluto (All Time)", f"{retorno_caixa_puro:.2f}%", f"R$ {caixa_total_gerado:,.2f}")
    c_perf2.metric("Selic Acumulada", f"{meta_acumulada_realizada:.2f}%", f"{meses_consolidados} Ciclos Vencidos", delta_color="off")
    c_perf3.metric("Fator Alpha (Alfa Gen.)", f"{alpha_gerado:+.2f}%", "Spread sobre a Selic" if alpha_gerado >= 0 else "Spread Negativo", delta_color="normal")
    c_perf4.metric("Provisão DARF a Pagar", f"R$ {darf_mes_atual:,.2f}", "Aberto no Ciclo de Tela", delta_color="inverse")
    c_perf5.metric("Ibovespa (30d)", f"{perf_ibov:.2f}%", "Benchmark Renda Variável")
    c_perf6.metric("Câmbio Dólar (30d)", f"{perf_usd:.2f}%", "Dólar PTAX (USD/BRL)")
