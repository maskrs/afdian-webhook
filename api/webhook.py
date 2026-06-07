"""
Vercel Serverless Function —— 爱发电 Webhook 转发到阿里云效

替代阿里云函数计算 FC（已收费），部署到 Vercel 免费版即可。
Vercel 免费额度足够 webhook 场景使用。
"""
import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error
from flask import Flask, request, jsonify

# ==================== 配置 ====================
# 在 Vercel 项目 -> Settings -> Environment Variables 中设置
FLOW_WEBHOOK_URL = os.environ.get('FLOW_WEBHOOK_URL', '')

# ==================== 日志 ====================
logger = logging.getLogger()
logger.setLevel(logging.INFO)

app = Flask(__name__)


def forward_to_flow(order_id: str, order_data: dict):
    """转发完整订单数据到阿里云效 Flow

    双重保障：JSON body + URL 查询参数同时发送。
    """
    if not FLOW_WEBHOOK_URL:
        logger.warning('FLOW_WEBHOOK_URL 未配置，跳过转发')
        return

    amount = order_data.get('total_amount', order_data.get('show_amount', '0'))
    remark = order_data.get('remark', '')
    user_id = order_data.get('user_id', '')
    plan_id = order_data.get('plan_id', '')
    sku_id = order_data.get('sku_id', '')
    month = order_data.get('month', '')

    # URL 查询参数（无需 Flow Webhook 配置参数映射也能工作）
    params = urllib.parse.urlencode({
        'order_id': order_id,
        'amount': str(amount),
        'remark': remark,
        'user_id': user_id,
        'plan_id': plan_id,
        'sku_id': sku_id,
        'month': str(month),
    }, doseq=True)
    url_with_params = FLOW_WEBHOOK_URL + '?' + params

    # JSON body（需要 Flow Webhook 配置参数映射，更可靠）
    payload = json.dumps({
        'order_id': order_id,
        'amount': amount,
        'remark': remark,
        'user_id': user_id,
        'plan_id': plan_id,
        'sku_id': sku_id,
        'month': month,
    }).encode('utf-8')

    req = urllib.request.Request(
        url_with_params,
        data=payload,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        logger.info(f'Flow 转发成功, status={resp.status}')
        resp.read()
    except urllib.error.URLError as e:
        logger.warning(f'Flow 转发失败: {e.reason}')
    except Exception as e:
        logger.warning(f'Flow 转发异常: {e}')


@app.route('/', methods=['POST'])
def webhook():
    """爱发电 Webhook 入口"""
    body = request.get_json(silent=True)
    if not body:
        logger.info('非 JSON 请求，忽略')
        return jsonify({'ec': 200, 'em': ''})

    ec = body.get('ec')
    data = body.get('data')

    if ec != 200:
        logger.info(f'非成功回调 ec={ec}')
        return jsonify({'ec': 200, 'em': ''})

    if not data or data.get('type') != 'order' or not data.get('order'):
        logger.info(f'非订单回调 type={data.get("type") if data else "none"}')
        return jsonify({'ec': 200, 'em': ''})

    order = data['order']
    order_id = order.get('out_trade_no', '') or ''
    logger.info(f'收到订单: {order_id}')

    forward_to_flow(order_id, order)

    return jsonify({'ec': 200, 'em': ''})


@app.route('/', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'ec': 200, 'em': 'ok'})


# ==================== Vercel 入口 ====================
# Vercel Python Serverless 会自动发现 Flask 的 `app` 变量
