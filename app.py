import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import hashlib
from supabase import create_client, Client

# ==========================================
# 0. CONFIGURAÇÃO DE IMPRESSÃO VISUAL (WHITE-LABEL)
# ==========================================
st.set_page_config(page_title="Gouldian Invest", page_icon="🦅", layout="wide")

# CSS para esconder Menu, Rodapé e Headers nativos do Streamlit
REMOVER_BRANDING_CSS = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .viewerBadge_container__1QSob {display: none !important;}
    </style>
"""
st.markdown(REMOVER_BRANDING_CSS, unsafe_allow_html=True)

# Mapeamento de meses para organização cronológica
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
    st.error("Erro de conexão com o servidor de dados.")
    st.stop()

def hash_senha(senha):
    return hashlib.sha256(senha.encode()).hexdigest()

# ==========================================
# 1. INICIALIZAÇÃO DA MEMÓRIA DO USUÁRIO
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'user_email' not in st.session_state:
    st.session_state['user_email'] = ""

def zerar_dados_financeiros():
    st.session_state['historico_rolagens'] = []
    st.session_state['caixa_acumulado_calls'] = 0.0
    st.session_state['caixa_proventos'] = 0.0
    st.session_state['mes_num'] = datetime.date.today().month
    st.session_state['ano_num'] = datetime.date.today().year
    st.session_state['preco_acao_tela'] = 0.0
    st.session_state['simulador_preco'] = 0.0

if 'historico_rolagens' not in st.session_state:
    zerar_dados_financeiros()

# ==========================================
# 2. INTERFACE DE ACESSO (LOGIN / CADASTRO)
# ==========================================
if not st.session_state['logged_in']:
    st.title("🦅 Gouldian Invest")
    st.markdown("Plataforma Quantitativa de Engenharia Financeira.")
    
    col_login, col_vazia = st.columns([1, 2])
    with col_login:
        st.subheader("Painel de Acesso")
        modo = st.radio("Selecione:", ["Login", "Criar Conta"], horizontal=True)
        
        email_input = st.text_input("E-mail").strip().lower()
        senha_input = st.text_input("Senha", type="password")
        
        if modo == "Login":
            if st.button("Entrar no Sistema", type="primary", use_container_width=True):
                if email_input and senha_input:
                    senha_criptografada = hash_senha(senha_input)
                    try:
                        resposta = supabase.table("usuarios").select("*").eq("email", email_input).execute()
                        if len(resposta.data) > 0:
                            user_db = resposta.data[0]
                            if user_db["senha"] == senha_criptografada:
                                st.session_state['logged_in'] = True
                                st.session_state['user_email'] = email_input
                                
                                dados_salvos = user_db.get("dados", {})
                                if dados_salvos:
                                    st.session_state['historico_rolagens'] = dados_salvos.get('historico_rolagens', [])
                                    st.session_state['caixa_acumulado_calls'] = dados_salvos.get('caixa_acumulado_calls', 0.0)
                                    st.session_state['caixa_proventos'] = dados_salvos.get('caixa_proventos', 0.0)
                                    st.session_state['mes_num'] = dados_salvos.get('mes_num', datetime.date.today().month)
                                    st.session_state['ano_num'] = dados_salvos.get('ano_num', datetime.date.today().year)
                                st.rerun()
                            else:
                                st.error("Senha incorreta.")
                        else:
                            st.error("Usuário não cadastrado.")
                    except Exception as err:
                        st.error(f"Erro de autenticação: {err}")
                else:
                    st.warning("Preencha todos os campos.")
        else:
            if st.button("Concluir Cadastro", type="primary", use_container_width=True):
                if email_input and senha_input:
                    try:
                        verifica = supabase.table("usuarios").select("email").eq("email", email_input).execute()
                        if len(verifica.data) > 0:
                            st.error("E-mail já se encontra em uso.")
                        else:
                            novo_user = {
                                "email": email_input,
                                "senha": hash_senha(senha_input),
                                "dados": {}
                            }
                            supabase.table("usuarios").insert(novo_user).execute()
                            st.success("Conta criada! Alterne para 'Login' para entrar.")
                    except Exception as err:
                        st.error(f"Erro ao salvar cadastro: {err}")
    st.stop()

# ==========================================
# 3. TELA PRINCIPAL (SISTEMA LOGADO)
# ==========================================
st.title("Gouldian Invest | Gestão de Collar Dinâmico")

col_user1, col_user2, col_user3 = st.columns([3, 1, 1])
nome_exibicao = st.session_state['user_email'].split('@')[0].capitalize()
col_user1.write(f"Sessão Ativa: **{nome_exibicao}** | Ambiente Seguro 🛡️")

if col_user2.button("💾 Salvar Dados na Nuvem", type="primary", use_container_width=True):
    dados_para_nuvem = {
        "historico_rolagens": st.session_state['historico_rolagens'],
        "caixa_acumulado_calls": st.session_state['caixa_acumulado_calls'],
        "caixa_proventos": st.session_state['caixa_proventos'],
        "mes_num": st.session_state['mes_num'],
        "ano_num": st.session_state['ano_num']
    }
    try:
        supabase.table("usuarios").update({"dados": dados_para_nuvem}).eq("email", st.session_state['user_email']).execute()
        st.success("Estudo salvo com sucesso!")
    except Exception as err:
        st.error(f"Falha ao salvar: {err}")

if col_user3.button("Sair do Sistema", use_container_width=True):
    st.session_state['logged_in'] = False
    zerar_dados_financeiros()
    st.rerun()

st.markdown("---")

# ==========================================
# 4. BARRA LATERAL (MONITOR E BENCHMARK)
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
            st.session_state['simulador_preco'] = float(preco_atual) 
            st.rerun()
        except:
            st.sidebar.error("Ticker inválido ou fora do ar.")

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

# Escolha do mês inicial caso o histórico esteja zerado
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Cronograma da Operação")
if len(st.session_state['historico_rolagens']) == 0:
    index_mes_atual = st.session_state['mes_num'] - 1
    mes_selecionado = st.sidebar.selectbox("Mês de Início", LISTA_MESES, index=index_mes_atual)
    st.session_state['mes_num'] = LISTA_MESES.index(mes_selecionado) + 1
    st.session_state['ano_num'] = st.sidebar.number_input("Ano de Início", value=st.session_state['ano_num'], step=1)
st.sidebar.info(f"Competência Atual: **{LISTA_MESES[st.session_state['mes_num']-1]}/{st.session_state['ano_num']}**")

# ==========================================
# FASE 1: AQUISIÇÃO E PROTEÇÃO
# ==========================================
st.header(f"📦 Fase 1: Montagem da Estrutura — {LISTA_MESES[st.session_state['mes_num']-1]}/{st.session_state['ano_num']}")
col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("1. Ativo Base")
    # Uso de value=None para deixar o campo totalmente limpo para digitação direta
    preco_acao_raw = st.number_input("Preço de Compra da Ação (R$)", value=None, placeholder="Digite o preço...", format="%.2f")
    qtd_raw = st.number_input("Quantidade de Ações", value=None, placeholder="Ex: 1000", step=100)
    
    preco_acao = preco_acao_raw if preco_acao_raw is not None else 0.0
    qtd = qtd_raw if qtd_raw is not None else 0

with col2:
    st.subheader("2. Seguro Longo (Put)")
    ticker_put = st.text_input("Código da Put", value="", placeholder="Ex: PETRR454")
    preco_put_raw = st.number_input("Prêmio Pago na Put (R$)", value=None, placeholder="Ex: 3.43", format="%.2f")
    strike_put_raw = st.number_input("Strike da Put (R$)", value=None, placeholder="Ex: 49.46", format="%.2f")
    
    preco_put = preco_put_raw if preco_put_raw is not None else 0.0
    strike_put = strike_put_raw if strike_put_raw is not None else 0.0

# Inicialização de variáveis calculadas
volume_acao = volume_put = tx_b3_entrada_acao = tx_b3_entrada_put = taxas_iniciais_totais = 0.0
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
    st.subheader("3. Gestão Patrimonial")
    st.markdown(f"**Desembolso Inicial Sacrificado:** R$ {custo_base_bruto:,.2f}")
    st.info(f"**Amortização Líquida Acumulada:** R$ {caixa_total_gerado:,.2f}")
    st.metric("Custo de Linha Ajustado", f"R$ {custo_base_ajustado:,.2f}", f"PM: R$ {preco_medio_atual:.2f}", delta_color="inverse")
    st.warning(f"🎯 **Strike de Call Eficiente:** R$ {strike_minimo:.2f}")

st.markdown("---")

# ==========================================
# FASE 2: ROLAGENS E RENDIMENTOS
# ==========================================
st.header("⚡ Fase 2: Distribuição de Caixa Mensal")
tab1, tab2 = st.tabs(["Lançamento de Call Mensal", "Proventos Declarados"])

with tab1:
    col4, col5 = st.columns([1, 2])
    with col4:
        ticker_call = st.text_input("Código da Call Curta", value="", placeholder="Ex: PETRF54")
        strike_call_raw = st.number_input("Strike da Call Lançada (R$)", value=None, placeholder="Ex: 54.19", format="%.2f")
        premio_call_raw = st.number_input("Prêmio Bruto Recebido (R$)", value=None, placeholder="Ex: 0.25", format="%.2f")
        
        strike_call = strike_call_raw if strike_call_raw is not None else 0.0
        premio_call = premio_call_raw if premio_call_raw is not None else 0.0

    volume_call = premio_call * qtd
    receita_liquida_call_pre_ir = volume_call - (volume_call * emol_opcao) - (corretagem if corretagem > 0 else 0.0)
    ir_isolado_call_po = receita_liquida_call_pre_ir * ir_opcoes
    receita_realmente_liquida_call = receita_liquida_call_pre_ir - ir_isolado_call_po

    with col5:
        st.write("")
        st.success(f"💸 Crédito Líquido de Lançamento (D+1): **R$ {receita_liquida_call_pre_ir:,.2f}**")
        st.caption(f"*(Cenário Virando Pó: Provisão de DARF de R$ {ir_isolado_call_po:,.2f} | Líquido para amortização: R$ {receita_realmente_liquida_call:,.2f})*")
        if strike_call > 0 and strike_call < strike_minimo:
            st.error("🚨 Atenção: O Strike selecionado viola o limite mínimo de proteção patrimonial!")

with tab2:
    c_prov1, c_prov2, c_prov3 = st.columns(3)
    with c_prov1:
        div_brutos_raw = st.number_input("Dividendos Recebidos (Isentos R$)", value=None, placeholder="0.00", format="%.2f")
        dividendos_brutos = div_brutos_raw if div_brutos_raw is not None else 0.0
    with c_prov2:
        jscp_brutos_raw = st.number_input("JSCP Bruto Declarado (R$)", value=None, placeholder="0.00", format="%.2f")
        jscp_bruto = jscp_brutos_raw if jscp_brutos_raw is not None else 0.0
    
    ir_jscp = jscp_bruto * ir_jscp_tax
    total_proventos_liquidos = dividendos_brutos + (jscp_bruto - ir_jscp)
    
    with c_prov3:
        st.info(f"Retenção de IR na Fonte (JSCP): **R$ -{ir_jscp:.2f}**")
        st.success(f"Total Líquido Disponível: **R$ {total_proventos_liquidos:.2f}**")

st.markdown("---")

# ==========================================
# FASE 3 E 4: PAYOFF E AUDITORIA CRONOLÓGICA
# ==========================================
st.header("🔮 Fase 3: Simulador Patrimonial e Auditoria")

max_slider = float(preco_acao * 2.0) if preco_acao > 0 else 100.0
valor_default = min(st.session_state.get('simulador_preco', float(preco_acao)), max_slider)

preco_vencimento = st.slider("Preço Estimado do Ativo no Vencimento (R$)", min_value=0.0, max_value=max_slider, value=float(valor_default), step=0.10)
st.session_state['simulador_preco'] = preco_vencimento

if preco_vencimento > strike_put and strike_put > 0:
    valor_residual_put = 0.0
else:
    valor_residual_put_raw = st.number_input("Valor de Mercado Residual da Put (R$)", value=None, placeholder="0.00", format="%.2f")
    valor_residual_put = valor_residual_put_raw if valor_residual_put_raw is not None else 0.0

receita_venda_put_residual = valor_residual_put * qtd
deseja_exercer_put = False
if preco_vencimento <= strike_put and strike_put > 0:
    deseja_exercer_put = st.checkbox("Acionar intencionalmente a Put de proteção para liquidação total da estrutura", value=False)

receita_venda_ativo = taxa_saida_b3 = corretagem_saida = 0.0
cenario_nome = "Aguardando Parâmetros de Entrada"

if qtd > 0:
    if preco_vencimento >= strike_call and strike_call > 0:
        cenario_nome = "🚀 EXERCÍCIO FORÇADO NA CALL (Venda no Strike)"
        receita_venda_ativo = strike_call * qtd
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        receita_venda_put_residual = 0.0 
    elif deseja_exercer_put:
        cenario_nome = "🛡️ EXECUÇÃO DA SALVAGUARDA (Venda no Strike da Put)"
        receita_venda_ativo = strike_put * qtd  
        taxa_saida_b3 = receita_venda_ativo * taxa_ex_b3 
        corretagem_saida = corretagem if corretagem > 0 else 0.0
        receita_venda_put_residual = 0.0  
    else:
        cenario_nome = "⚖️ MANUTENÇÃO DE CARTEIRA (Ação Mantida / Opção Vencendo Pó)"
        receita_venda_ativo = preco_vencimento * qtd 
        taxa_saida_b3 = receita_venda_ativo * emol_acao 
        corretagem_saida = corretagem if corretagem > 0 else 0.0

lucro_bruto_operacao = (receita_venda_ativo + receita_liquida_call_pre_ir + receita_venda_put_residual) - (custo_base_ajustado + taxa_saida_b3 + corretagem_saida)
ir_devido_operacao = max(0.0, lucro_bruto_operacao * ir_opcoes)
lucro_liquido_final = lucro_bruto_operacao - ir_devido_operacao

rentabilidade_sobre_capital_inicial = (lucro_liquido_final / custo_base_bruto) * 100 if custo_base_bruto > 0 else 0.0

# Cálculo dinâmico do número de meses decorridos a partir do histórico para bater com a Selic
meses_decorridos = len(st.session_state['historico_rolagens']) + 1
if "Simples" in tipo_juros:
    meta_acumulada_mes = meta_mensal * meses_decorridos
else:
    meta_acumulada_mes = (((1 + juros_liquido_am) ** meses_decorridos) - 1) * 100

st.markdown(f"#### Comportamento da Estrutura: **{cenario_nome}**")

c_res1, c_res2, c_res3 = st.columns(3)
c_res1.metric("Resultado Líquido Estimado", f"R$ {lucro_liquido_final:,.2f}")
c_res2.metric("Yield on Cost (Retorno s/ Cap. Inicial)", f"{rentabilidade_sobre_capital_inicial:.2f}%")
c_res3.metric(f"Meta Balizada Selic Acumulada", f"{meta_acumulada_mes:.2f}%")

st.write("")
c_btn1, c_btn2 = st.columns(2)

with c_btn1:
    if st.button("➕ Consolidar Mês e Avançar Cronograma Cronológico", use_container_width=True):
        if qtd > 0:
            caixa_gerado_no_mes = receita_realmente_liquida_call + total_proventos_liquidos
            caixa_total_acumulado_projetado = st.session_state['caixa_acumulado_calls'] + st.session_state['caixa_proventos'] + caixa_gerado_no_mes
            retorno_acum_capital_ini = (caixa_total_acumulado_projetado / custo_base_bruto) * 100
            
            # Registra competência formatada
            competencia_texto = f"{LISTA_MESES[st.session_state['mes_num']-1]}/{st.session_state['ano_num']}"
            
            novo_registro = {
                "Competência": competencia_texto,
                "Call Ref.": ticker_call if ticker_call else "-",
                "Renda Opção Liq.": receita_realmente_liquida_call,
                "Dividendos/JSCP Liq.": total_proventos_liquidos,
                "Fluxo de Caixa Mês": caixa_gerado_no_mes,
                "PM Depreciado": preco_medio_atual - (caixa_gerado_no_mes / qtd),
                "Retorno Real Acum.": retorno_acum_capital_ini
            }
            
            st.session_state['historico_rolagens'].append(novo_registro)
            st.session_state['caixa_acumulado_calls'] += receita_realmente_liquida_call
            st.session_state['caixa_proventos'] += total_proventos_liquidos
            
            # Regra Cronológica de Virada de Ano Automática
            if st.session_state['mes_num'] == 12:
                st.session_state['mes_num'] = 1
                st.session_state['ano_num'] += 1
            else:
                st.session_state['mes_num'] += 1
                
            st.rerun()
        else:
            st.error("Monte a Fase 1 definindo Preço e Quantidade para poder consolidar históricos.")

with c_btn2:
    if st.button("🛑 Apagar Estudo e Resetar Cronograma", type="primary", use_container_width=True):
        zerar_dados_financeiros()
        st.rerun()

if st.session_state['historico_rolagens']:
    st.subheader("📊 Relatório Cronológico de Amortização Patrimonial")
    df_historico = pd.DataFrame(st.session_state['historico_rolagens'])
    
    cols_moeda = ["Renda Opção Liq.", "Dividendos/JSCP Liq.", "Fluxo de Caixa Mês", "PM Depreciado"]
    for col in cols_moeda:
        df_historico[col] = df_historico[col].apply(lambda x: f"R$ {x:.2f}")
    df_historico["Retorno Real Acum."] = df_historico["Retorno Real Acum."].apply(lambda x: f"{x:.2f}%")
    
    st.dataframe(df_historico, use_container_width=True, hide_index=True)
