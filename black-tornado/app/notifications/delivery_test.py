"""Explicit, labeled Telegram delivery test. Never alters trading statistics."""
import json,time
from pathlib import Path
from types import SimpleNamespace
from app.notifications.telegram import TelegramClient
from app.engine.outcome_tracker import OutcomeResult

async def run_delivery_test(settings,output,send=False):
    if not send: raise ValueError('Use --send to explicitly authorize TEST messages to the configured chat')
    client=TelegramClient(settings)
    report={'test_only':True,'trades_created':0,'scope':'Telegram permission + production formatter + actual sendMessage acknowledgement; not market-scan/settlement validation','started_ts':time.time()}
    try:
        if not client.configured: raise ValueError('Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID securely')
        async def api(method,data=None):
            response=await client._client.post(f'https://api.telegram.org/bot{client.token}/{method}',json=data or {})
            body=response.json()
            if response.status_code!=200 or not body.get('ok'): raise RuntimeError('Telegram preflight rejected '+method+'; HTTP '+str(response.status_code))
            return body['result']
        me=await api('getMe')
        chat=await api('getChat',{'chat_id':client.chat_id})
        membership=await api('getChatMember',{'chat_id':client.chat_id,'user_id':me['id']})
        if chat.get('type')=='channel' and not (membership.get('status')=='creator' or (membership.get('status')=='administrator' and membership.get('can_post_messages'))):
            raise RuntimeError('Bot must be channel administrator with permission to post messages')
        report.update(bot_username=me.get('username'),chat_id=chat['id'],chat_type=chat.get('type'),permission_status=membership.get('status'))
        entry=(int(time.time())//60+1)*60
        signal=SimpleNamespace(signal_no=0,symbol='EURUSD-OTC',direction='CALL',entry_ts=entry,expiry_ts=entry+60,score=82,strategy='BT03',snapshot={'details':{'test_only':True,'strategy_name':'ADAPTIVE_PULLBACK'}},sent_ts=None)
        report['signal_sent']=await client.send_signal(signal)
        report['signal_message_id']=client.last_message_id if report['signal_sent'] else None
        report['signal_ack_ms']=client.last_latency_ms
        if not report['signal_sent']: raise RuntimeError(client.last_error or 'Signal test not acknowledged; no retry')
        result=OutcomeResult('UNVERIFIED','feed_estimated',None,None,None,None,'Delivery test only; no trade or boundary-price result exists.')
        report['result_sent']=await client.send_result(signal,result)
        report['result_message_id']=client.last_message_id if report['result_sent'] else None
        report['result_ack_ms']=client.last_latency_ms
        if not report['result_sent']: raise RuntimeError(client.last_error or 'Result test not acknowledged; no retry')
        report['success']=True
    except Exception as exc:
        # Exception URL/message might contain token: store safe type only.
        report['success']=False;report['error_type']=type(exc).__name__
    finally:
        report['completed_ts']=time.time()
        await client.close()
        path=Path(output);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2))
    return report
