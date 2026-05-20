import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO VISUAL COMPLETA (WHITE-LABEL)
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

REMOVER_BRANDING_CSS = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none !important;}
    </style>
"""
st.markdown(REMOVER_BRANDING_CSS, unsafe_allow_html=True)

LISTA_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
               "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]

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
    st.session_state['mes_num'] = datetime.date.today().month
    st.session_state['ano_num'] = datetime.date.today().year
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

def carregar_estrategia_salva(nome, pkg):
    st.session_state['nome_estrategia_atual'] = nome
    st.session_state['historico_rolagens'] = pkg.get('historico_rolagens', [])
    st.session_state['mes_num'] = pkg.get('mes_num', datetime.date.today().month)
    st.session_state['ano_num'] = pkg.get('ano_num', datetime.date.today().year)
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

# ==========================================
# 1. CONTROLE DE AMBIENTE E SUPABASE AUTH
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""
if 'preco_acao_tela' not in st.session_state:
    st.session_state['preco_acao_tela'] = 0.0

# PERSISTÊNCIA DE LOGIN SEGURA VIA TOKEN JWT
if "access_token" in st.query_params and not st.session_state['logged_in']:
    token_jwt = st.query_params["access_token"]
    try:
        user_auth = supabase.auth.get_user(token_jwt)
        if user_auth and user_auth.user:
            email_logado = user_auth.user.email
            st.session_state['logged_in'] = True
            st.session_state['username'] = email_logado.split('@')[0].capitalize()
            st.session_state['user_email_completo'] = email_logado
            
            # Busca as estratégias salvas do usuário na tabela
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
    st.title("🦅 Gouldian Invest")
    st.markdown("Plataforma Quantitativa de Engenharia Financeira de Derivativos.")
    
    col_login, col_vazia = st.columns([1, 2])
    with col_login:
        st.subheader("Painel de Acesso")
        modo = st.radio("Selecione:", ["Login", "Criar Conta", "Esqueci a Senha"], horizontal=True)
        
        if modo in ["Login", "Criar Conta"]:
            email_input = st.text_input("E-mail").strip().lower()
            senha_input = st.text_input("Senha", type="password")
            
            if modo == "Login":
                if st.button("Entrar no Sistema", type="primary", use_container_width=True):
                    if email_input and senha_input:
                        try:
                            # LOGIN NATIVO SUPABASE
                            auth_response = supabase.auth.sign_in_with_password({"email": email_input, "password": senha_input})
                            
                            st.session_state['logged_in'] = True
                            st.session_state['username'] = email_input.split('@')[0].capitalize()
                            st.session_state['user_email_completo'] = email_input
                            # Salva o token na URL para refresh
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
                        except Exception as err:
                            st.error(f"Erro de autenticação. Verifique e-mail e senha ou se a conta foi confirmada.")
                    else:
                        st.warning("Preencha todos os campos.")
            
            elif modo == "Criar Conta":
                if st.button("Concluir Cadastro", type="primary", use_container_width=True):
                    if email_input and senha_input:
                        try:
                            # CADASTRO NATIVO SUPABASE
                            auth_response = supabase.auth.sign_up({"email": email_input, "password": senha_input})
                            
                            # Cria o espaço do usuário no banco de dados para salvar estratégias
                            st.session_state['dados_nuvem'] = {"estrategias": {}}
                            supabase.table("usuarios").insert({"email": email_input, "dados": st.session_state['dados_nuvem']}).execute()
                            
                            st.success("✅ Conta criada com sucesso! Verifique seu e-mail para validar a conta, ou tente fazer login direto (dependendo das configurações do seu projeto).")
                        except Exception as err:
                            st.error(f"Erro ao criar conta (a senha deve ter no mínimo 6 caracteres). Detalhes: {err}")
        
        elif modo == "Esqueci a Senha":
            email_rec = st.text_input("E-mail de recuperação").strip().lower()
            if st.button("Enviar link de recuperação", type="primary", use_container_width=True):
                if email_rec:
                    try:
                        # DISPARO DE EMAIL DE RECUPERAÇÃO NATIVO
                        supabase.auth.reset_password_for_email(email_rec, options={"redirect_to": "https://calculadoracollarb.streamlit.app/"})
                        st.success("📩 Instruções enviadas! Verifique sua caixa de entrada ou spam.")
                    except Exception as err:
                        st.error(f"Erro ao solicitar recuperação. Tente novamente.")
                else:
                    st.warning("Preencha o e-mail.")
                    
    st.stop()

# ==========================================
# 2. SEÇÃO DE PERFIL E GERENCIAMENTO DE PROJETOS (LOADER)
# ==========================================
st.title("Gouldian Invest | Gestão de Collar Dinâmico")
st.write(f"Sessão Ativa: **{st.session_state['username']}** | Conexão Segura e Criptografada 🛡️")

with st.expander("👤 Meu Perfil & Estratégias Salvas", expanded=True):
    dict_estrategias = st.session_state['dados_nuvem'].get("estrategias", {})
    opcoes_projeto = ["-- Criar Nova Estratégia (Tela Limpa) --"] + list(dict_estrategias.keys())
    
    if 'projeto_index' not in st.session_state:
        st.session_state['projeto_index'] = 0
        
    projeto_escolhido = st.selectbox("📁 Selecionar Estratégia Cadastrada no Perfil:", opcoes_projeto, index=st.session_state['projeto_index'])
    
    if 'ultimo_projeto_escolhido' not in st.session_state or st.session_state['ultimo_projeto_escolhido'] != projeto_escolhido:
        st.session_state['ultimo_projeto_escolhido'] = projeto_escolhido
        st.session_state['projeto_index'] = opcoes_projeto.index(projeto_escolhido)
        if projeto_escolhido == "-- Criar Nova Estratégia (Tela Limpa) --":
            inicializar_estrategia_vazia()
        else:
            carregar_estrategia_salva(projeto_escolhido, dict_estrategias[projeto_escolhido])
        st.rerun()

st.markdown("---")

col_top1, col_top2 = st.columns([8, 2])
if col_top2.button("Sair da Conta (Logout)", use_container_width=True):
    supabase.auth.sign_out()
    st.session_state['logged_in'] = False
    st.query_params.clear()
    st.rerun()

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
# 3. BARRA LATERAL (MONITOR E BENCHMARK)
# ==========================================
st.sidebar.header("🔍 Monitor de Mercado")
ticker_acao = st.sidebar.text_input("Ticker do Ativo", value="", placeholder="Ex: PETR4.SA")
st.sidebar.markdown(f"**Preço de Tela Atual:** R$ {st.session_state['preco_acao_tela']:.2f}")

if st.sidebar.button("Buscar Cotação"):
    if ticker_acao:
        try:
            acao = yf.Ticker(ticker_acao)
            preco_atual = acao.history(period="1d")['Close'].iloc[-1]
            st.session_state['preco_acao_tela'] = float(preco_atual)
            st.rerun()
        except:
            st.sidebar.error("Ativo indisponível no momento.")

with st.sidebar.expander("⚙️ Custos Operacionais e IR", expanded=False):
    ir_opcoes = st.number_input("IR Opções (%)", value=15.0, step=0.5) / 100
    ir_jscp_tax = st.number_input("IR JSCP (%)", value=15.0, step=0.5) / 100
    emol_acao = st.number_input("Emolumentos Ação (%)", value=0.0325, format="%.4f") / 100
    emol_opcao = st.number_input("Emolumentos Opção (%)", value=0.0375, format="%.4f") / 100
    corretagem = st.number_input("Corretagem Fixa (R$)", value=0.00, step=1.0)
    taxa_ex_b3 = st.number_input("Taxa Exercício B3 (%)", value=0.5, step=0.1) / 100

with st.sidebar.expander("🏦 Benchmark Selic", expanded=False):
    juros_bruto_aa = st.number_input("Selic Bruta (% a.a.)", value=14.50, step=0.1) / 100
    ir_renda_fixa = st.number_input("IR Renda Fixa (%)", value=22.5, step=0.5) / 100
    juros_liquido_aa = juros_bruto_aa * (1 - ir_renda_fixa)
    tipo_juros = st.sidebar.radio("Regime Tributário/Selic", ["Simples (Conservador)", "Composto (Equivalente)"])
    if "Simples" in tipo_juros:
        juros_liquido_am = juros_liquido_aa / 12
    else:
        juros_liquido_am = ((1 + juros_liquido_aa) ** (1/12)) - 1
    meta_mensal = juros_liquido_am * 100

# ==========================================
# FASE 1: MONTAGEM DO MODELO E CRONOLOGIA
# ==========================================
st.header("📦 Fase 1: Parâmetros e Alvos da Operação")

col_cron1, col_cron2, col_vazio_cron = st.columns([1, 1, 2])
with col_cron1:
    index_mes_atual = st.session_state['mes_num'] - 1
    mes_selecionado = st.selectbox("Mês de Referência", LISTA_MESES, index=index_mes_atual)
    st.session_state['mes_num'] = LISTA_MESES.index(mes_selecionado) + 1
with col_cron2:
    st.session_state['ano_num'] = st.number_input("Ano de Referência", value=st.session_state['ano_num'], step=1)

st.write("")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. Ativo Base")
    preco_acao_raw = st.number_input("Preço de Compra da Ação (R$)", value=st.session_state['val_preco_acao'], placeholder="Digite o preço...", format="%.2f")
    qtd_raw = st.number_input("Quantidade de Ações", value=st.session_state['val_qtd'], placeholder="Ex: 1000", step=100)
    
    preco_acao = preco_acao_raw if preco_acao_raw is not None else 0.0
    qtd = qtd_raw if qtd_raw is not None else 0

with col2:
    st.subheader("2. Seguro Longo (Put)")
    ticker_put = st.text_input("Código da Put", value=st.session_state['val_ticker_put'], placeholder="Ex: PETRR454")
    preco_put_raw = st.number_input("Prêmio Pago na Put (R$)", value=st.session_state['val_preco_put'], placeholder="Ex: 3.43", format="%.2f")
    strike_put_raw = st.number_input("Strike da Put (R$)", value=st.session_state['val_strike_put'], placeholder="Ex: 49.46", format="%.2f")
    
    preco_put = preco_put_raw if preco_put_raw is not None else 0.0
    strike_put = strike_put_raw if strike_put_raw is not None else 0.0

volume_acao = volume_put = tx_b3_entrada_acao = tx_b3_entrada_put = taxas_iniciais_totais = 0.0
custo_base_bruto = custo_base_ajustado = strike_minimo = preco_medio_atual = meta_financeira_12m = 0.0

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
    meta_financeira_12m = custo_base_bruto * (1 + juros_liquido_aa)

with col3:
    st.subheader("3. Gestão Patrimonial")
    st.markdown(f"**Capital Inicial Sacrificado:** R$ {custo_base_bruto:,.2f}")
    st.info(f"**Amortização Líquida Total:** R$ {caixa_total_gerado:,.2f}")
    st.metric("Custo de Linha Ajustado", f"R$ {custo_base_ajustado:,.2f}", f"PM Real: R$ {preco_medio_atual:.2f}", delta_color="inverse")
    st.warning(f"🎯 **Strike Mínimo Ideal:** R$ {strike_minimo:.2f}")
    if meta_financeira_12m > 0:
        st.info(f"💰 **Alvo Renda Fixa (12M):** R$ {meta_financeira_12m:,.2f}")

st.markdown("---")

# ==========================================
# FASE 2: REMUNERAÇÃO DE CAIXA MENSAL
# ==========================================
st.header("⚡ Fase 2: Distribuição de Caixa Mensal")
tab1, tab2 = st.tabs(["Lançamento de Call Mensal", "Proventos Recebidos"])

with tab1:
    col4, col5 = st.columns([1, 2])
    with col4:
        ticker_call = st.text_input("Código da Call Curta", value=st.session_state['val_ticker_call'], placeholder="Ex: PETRF54")
        strike_call_raw = st.number_input("Strike da Call Lançada (R$)", value=st.session_state['val_strike_call'], placeholder="Ex: 54.19", format="%.2f")
        premio_call_raw = st.number_input("Prêmio Bruto Recebido (R$)", value=st.session_state['val_premio_call'], placeholder="Ex: 0.25", format="%.2f")
        
        strike_call = strike_call_raw if strike_call_raw is not None else 0.0
        premio_call = premio_call_raw if premio_call_raw is not None else 0.0

    volume_call = premio_call * qtd
    custos_atrito_call = (volume_call * emol_opcao) + (corretagem if corretagem > 0 else 0.0)
    receita_liquida_call_pre_ir = volume_call - custos_atrito_call
    ir_isolado_call_po = receita_liquida_call_pre_ir * ir_opcoes
    receita_realmente_liquida_call = receita_liquida_call_pre_ir - ir_isolado_call_po

    with col5:
        st.write("")
        st.success(f"💸 Crédito Líquido Operacional (D+1): **R$ {receita_liquida_call_pre_ir:,.2f}**")
        st.caption(f"*(Amortização efetiva descontando IR da Opção: R$ {receita_realmente_liquida_call:,.2f})*")
        
        if premio_call > 0 and custo_base_bruto > 0:
            rendimento_call_mes = (receita_realmente_liquida_call / custo_base_bruto) * 100
            if rendimento_call_mes < meta_mensal:
                st.warning(f"⚠️ **Atenção (Custo de Oportunidade):** A taxa líquida desta Call ({rendimento_call_mes:.2f}%) está **abaixo** da Selic do mês ({meta_mensal:.2f}%). Tente um prêmio maior.")
            else:
                st.info(f"🎯 **Prêmio Eficiente:** A taxa líquida desta Call ({rendimento_call_mes:.2f}%) supera a Selic mensal ({meta_mensal:.2f}%).")
        
        if strike_call > 0 and strike_call < strike_minimo:
            st.error("🚨 O Strike selecionado reduz a margem mínima de segurança do Capital Inicial!")

with tab2:
    c_prov1, c_prov2, c_prov3 = st.columns(3)
    with c_prov1:
        div_brutos_raw = st.number_input("Dividendos Recebidos (Isentos R$)", value=st.session_state['val_dividendos'], placeholder="0.00", format="%.2f")
        dividendos_brutos = div_brutos_raw if div_brutos_raw is not None else 0.0
    with c_prov2:
        jscp_brutos_raw = st.number_input("JSCP Bruto Recebido (R$)", value=st.session_state['val_jscp'], placeholder="0.00", format="%.2f")
        jscp_bruto = jscp_brutos_raw if jscp_brutos_raw is not None else 0.0
    
    ir_jscp = jscp_bruto * ir_jscp_tax
    total_proventos_liquidos = dividendos_brutos + (jscp_bruto - ir_jscp)
    
    with c_prov3:
        st.info(f"Retenção de IR na Fonte (JSCP): **R$ -{ir_jscp:.2f}**")
        st.success(f"Disponível Líquido: **R$ {total_proventos_liquidos:.2f}**")

st.markdown("---")

# ==========================================
# FASE 3: SIMULADOR DE PAYOFF COMPLETO
# ==========================================
st.header("🔮 Fase 3: Simulador Patrimonial de Payoff")

max_slider = float(preco_acao * 2.0) if preco_acao > 0 else 100.0

preco_vencimento = st.slider(
    "Preço Estimado do Ativo no Vencimento (R$)", 
    min_value=0.0, 
    max_value=max_slider, 
    value=float(preco_acao if preco_acao > 0 else 10.0), 
    step=0.10,
    key="slider_payoff_estavel"
)

if preco_vencimento > strike_put and strike_put > 0:
    valor_residual_put = 0.0
else:
    valor_residual_put_raw = st.number_input("Valor Comercial Residual da Put (R$)", value=None, placeholder="0.00", format="%.2f")
    valor_residual_put = valor_residual_put_raw if valor_residual_put_raw is not None else 0.0

receita_venda_put_residual = valor_residual_put * qtd
deseja_exercer_put = False
if preco_vencimento <= strike_put and strike_put > 0:
    deseja_exercer_put = st.checkbox("Acionar intencionalmente o Direito de Venda (Put) para liquidação da linha de risco")

receita_venda_ativo = taxa_saida_b3 = corretagem_saida = 0.0
status_put = "Em vigor / Protegendo carteira"
status_call = "Em aberto"
cenario_nome = "Aguardando Alocação da Fase 1"

if qtd > 0:
    if preco_vencimento >= strike_call and strike_call > 0:
        cenario_nome = "🚀 EXERCÍCIO INTEGRAL NA CALL (Venda Compulsória no Alvo)"
        receita_venda_ativo = strike_call * qtd
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        status_put = "Ficou fora do dinheiro (Virou pó / Custo perdido)"
        status_call = f"Exercida a R$ {strike_call:.2f}"
        receita_venda_put_residual = 0.0 
    elif deseja_exercer_put:
        cenario_nome = "🛡️ EXECUÇÃO DO SEGURO DE PROTEÇÃO (Venda no Strike da Put)"
        receita_venda_ativo = strike_put * qtd  
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        status_put = f"Exercida voluntariamente a R$ {strike_put:.2f}"
        status_call = "Venceu sem valor (Virou Pó)"
        receita_venda_put_residual = 0.0  
    else:
        cenario_nome = "⚖️ MANUTENÇÃO E ROLAGEM DE POSIÇÃO (Ativo Retido / Call Virou Pó)"
        receita_venda_ativo = preco_vencimento * qtd 
        taxa_saida_b3 = receita_venda_ativo * emol_acao 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        status_put = f"Mantida na carteira (Valorizada em tela por R$ {valor_residual_put:.2f})"
        status_call = "Venceu sem valor (Virou Pó)"

lucro_bruto_operacao = (receita_venda_ativo + receita_liquida_call_pre_ir + receita_venda_put_residual) - (custo_base_ajustado + taxa_saida_b3 + corretagem_saida)
ir_devido_operacao = max(0.0, lucro_bruto_operacao * ir_opcoes)
lucro_liquido_final = lucro_bruto_operacao - ir_devido_operacao

rentabilidade_sobre_capital_inicial = (lucro_liquido_final / custo_base_bruto) * 100 if custo_base_bruto > 0 else 0.0

meses_projetados = len(st.session_state['historico_rolagens']) + 1
if "Simples" in tipo_juros:
    meta_acumulada_projetada = meta_mensal * meses_projetados
else:
    meta_acumulada_projetada = (((1 + juros_liquido_am) ** meses_projetados) - 1) * 100

st.markdown(f"#### Comportamento da Estrutura: **{cenario_nome}**")

c_res1, c_res2, c_res3 = st.columns(3)
c_res1.metric("Resultado Líquido Estimado", f"R$ {lucro_liquido_final:,.2f}")
c_res2.metric("Yield on Cost (Retorno Global)", f"{rentabilidade_sobre_capital_inicial:.2f}%")
c_res3.metric(f"Meta Balizada Selic Projetada", f"{meta_acumulada_projetada:.2f}%")

st.markdown("---")

# ==========================================
# FASE 4: CONSOLIDAÇÃO E SALVAMENTO DE NUVEM
# ==========================================
st.header("⏳ Fase 4: Consolidação e Retenção em Nuvem")

c_btn1, c_btn2 = st.columns(2)
with c_btn1:
    if st.button("➕ Consolidar Competência no Histórico de Tabelas", use_container_width=True):
        if qtd > 0:
            competencia_texto = f"{LISTA_MESES[st.session_state['mes_num']-1]}/{st.session_state['ano_num']}"
            
            novo_registro = {
                "Competência": competencia_texto,
                "Call Ref.": ticker_call if ticker_call else "-",
                "Renda Opção Liq.": float(receita_realmente_liquida_call),
                "Dividendos/JSCP Liq.": float(total_proventos_liquidos),
                "_Strike Call": float(strike_call),
                "_Premio Bruto Call": float(volume_call),
                "_Custos B3 e Corretagem Call": float(custos_atrito_call),
                "_DARF Retido Call": float(ir_isolado_call_po),
                "_Dividendos Isentos": float(dividendos_brutos),
                "_JSCP Bruto": float(jscp_bruto),
                "_IR JSCP": float(ir_jscp)
            }
            st.session_state['historico_rolagens'].append(novo_registro)
            
            # Avanço de Cronologia Inteligente
            if st.session_state['mes_num'] == 12:
                st.session_state['mes_num'] = 1
                st.session_state['ano_num'] += 1
            else:
                st.session_state['mes_num'] += 1
            st.rerun()
        else:
            st.error("Insira o preço e a quantidade do Ativo Base para registrar dados.")

with c_btn2:
    if st.button("🛑 Limpar Estudo Atual da Tela", type="primary", use_container_width=True):
        inicializar_estrategia_vazia()
        st.rerun()

st.write("")

col_save1, col_save2 = st.columns([3, 1])
with col_save1:
    nome_projeto_salvar = st.text_input("Identificador/Nome Obrigatório para Gravar esta Estratégia", value=st.session_state['nome_estrategia_atual'], placeholder="Ex: PETR4 Collar Conservador 2026")
with col_save2:
    st.write("")
    st.write("")
    if st.button("💾 Gravar Estudo no Perfil", type="primary", use_container_width=True):
        if not nome_projeto_salvar.strip():
            st.error("❌ Bloqueado: Preencha um nome para a estratégia antes de salvar!")
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
                "mes_num": st.session_state['mes_num'],
                "ano_num": st.session_state['ano_num']
            }
            
            st.session_state['dados_nuvem']["estrategias"][nome_projeto_salvar.strip()] = dados_estrategia_atual
            st.session_state['nome_estrategia_atual'] = nome_projeto_salvar.strip()
            
            try:
                supabase.table("usuarios").update({"dados": st.session_state['dados_nuvem']}).eq("email", st.session_state['user_email_completo']).execute()
                st.success(f"🎉 Sucesso: Estratégia '{nome_projeto_salvar.strip()}' arquivada!")
                st.session_state['projeto_index'] = list(st.session_state['dados_nuvem']["estrategias"].keys()).index(nome_projeto_salvar.strip()) + 1
                st.rerun()
            except Exception as err:
                st.error(f"Erro ao salvar: {err}")

# ==========================================
# 5. TABELA DE AUDITORIA INTERATIVA E EXTRATO
# ==========================================
if st.session_state['historico_rolagens']:
    st.markdown("---")
    st.subheader("📊 Relatório Cronológico de Amortização Patrimonial")
    
    df_base = pd.DataFrame(st.session_state['historico_rolagens'])
    df_corrigido = st.data_editor(
        df_base,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "Competência": st.column_config.TextColumn("Competência", required=True),
            "Call Ref.": st.column_config.TextColumn("Call Ref."),
            "Renda Opção Liq.": st.column_config.NumberColumn("Renda Opção Liq.", format="R$ %.2f"),
            "Dividendos/JSCP Liq.": st.column_config.NumberColumn("Dividendos/JSCP Liq.", format="R$ %.2f"),
            "_Strike Call": None,
            "_Premio Bruto Call": None,
            "_Custos B3 e Corretagem Call": None,
            "_DARF Retido Call": None,
            "_Dividendos Isentos": None,
            "_JSCP Bruto": None,
            "_IR JSCP": None
        }
    )
    
    if not df_corrigido.equals(df_base):
        st.session_state['historico_rolagens'] = df_corrigido.to_dict(orient="records")
        st.rerun()

    st.write("")
    st.subheader("🧾 Extrato Mensal Detalhado")
    meses_consolidados_lista = [r["Competência"] for r in st.session_state['historico_rolagens']]
    
    if meses_consolidados_lista:
        mes_extrato = st.selectbox("Selecione o Mês para Auditoria:", meses_consolidados_lista)
        dados_mes = next((item for item in st.session_state['historico_rolagens'] if item["Competência"] == mes_extrato), None)
        
        if dados_mes:
            c_ext1, c_ext2, c_ext3 = st.columns(3)
            with c_ext1:
                st.markdown("**📊 Operação de Opções**")
                st.write(f"Prêmio Bruto: R$ {dados_mes.get('_Premio Bruto Call', 0.0):,.2f}")
                st.write(f"Custos/Corretagem: R$ -{dados_mes.get('_Custos B3 e Corretagem Call', 0.0):,.2f}")
                st.write(f"DARF (IR): R$ -{dados_mes.get('_DARF Retido Call', 0.0):,.2f}")
                st.info(f"**Líquido Opção:** R$ {dados_mes.get('Renda Opção Liq.', 0.0):,.2f}")
                
            with c_ext2:
                st.markdown("**💰 Eventos Corporativos**")
                st.write(f"Dividendos Isentos: R$ {dados_mes.get('_Dividendos Isentos', 0.0):,.2f}")
                st.write(f"JSCP Bruto: R$ {dados_mes.get('_JSCP Bruto', 0.0):,.2f}")
                st.write(f"IR Retido (JSCP): R$ -{dados_mes.get('_IR JSCP', 0.0):,.2f}")
                st.info(f"**Líquido Proventos:** R$ {dados_mes.get('Dividendos/JSCP Liq.', 0.0):,.2f}")
                
            with c_ext3:
                st.markdown("**🧾 Fechamento Consolidado**")
                caixa_bruto_total = dados_mes.get('_Premio Bruto Call', 0.0) + dados_mes.get('_Dividendos Isentos', 0.0) + dados_mes.get('_JSCP Bruto', 0.0)
                total_retencoes = dados_mes.get('_Custos B3 e Corretagem Call', 0.0) + dados_mes.get('_DARF Retido Call', 0.0) + dados_mes.get('_IR JSCP', 0.0)
                caixa_liquido_total = caixa_bruto_total - total_retencoes
                
                st.write(f"Total Bruto: R$ {caixa_bruto_total:,.2f}")
                st.write(f"Total Custos/Tributos: R$ -{total_retencoes:,.2f}")
                st.success(f"**Caixa Real Gerado:** R$ {caixa_liquido_total:,.2f}")

# ==========================================
# 6. PAINEL COMPARATIVO DE PERFORMANCE
# ==========================================
st.markdown("---")
st.subheader("🏆 Painel Comparativo de Performance Absoluta")

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
if meses_consolidados == 0:
    meta_acumulada_realizada = 0.0
else:
    if "Simples" in tipo_juros:
        meta_acumulada_realizada = meta_mensal * meses_consolidados
    else:
        meta_acumulada_realizada = (((1 + juros_liquido_am) ** meses_consolidados) - 1) * 100

alpha_gerado = retorno_caixa_puro - meta_acumulada_realizada
darf_mes_atual = ir_isolado_call_po if 'ir_isolado_call_po' in locals() else 0.0

c_perf1, c_perf2, c_perf3, c_perf4, c_perf5, c_perf6 = st.columns(6)

c_perf1.metric(
    label="Caixa Gerado Consolidado", 
    value=f"{retorno_caixa_puro:.2f}%", 
    delta=f"R$ {caixa_total_gerado:,.2f}"
)
c_perf2.metric(
    label="Selic Líquida Consolidada", 
    value=f"{meta_acumulada_realizada:.2f}%", 
    delta=f"{meses_consolidados} Meses",
    delta_color="off"
)
c_perf3.metric(
    label="Alpha (Excesso de Retorno)", 
    value=f"{alpha_gerado:+.2f}%", 
    delta="Acima da Selic" if alpha_gerado >= 0 else "Abaixo da Selic",
    delta_color="normal"
)
c_perf4.metric(
    label="DARF Opções (Mês Atual)", 
    value=f"R$ {darf_mes_atual:,.2f}", 
    delta="Provisão Fiscal",
    delta_color="inverse"
)
c_perf5.metric(
    label="Ibovespa (Ações)", 
    value=f"{perf_ibov:.2f}%", 
    delta="1 Mês"
)
c_perf6.metric(
    label="Câmbio Dólar (USD/BRL)", 
    value=f"{perf_usd:.2f}%", 
    delta="1 Mês"
)
