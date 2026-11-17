import test from 'node:test';
import assert from 'node:assert/strict';
import { invitationMessage, invitationSummary, invitationCommonMessage, exactInvitationItems, invitationLinkMessage } from '../../web/js/screens/admin/invitation-presentation.js';
for (const code of ['invalid_email','questionnaire_unconfirmed','questionnaire_incomplete','organization_changed','member_unavailable','permission_denied','mail_not_configured','provider_rejected','provider_recipient','provider_sender','provider_access','provider_limit','provider_temporary','context_changed','operation_mismatch','link_used','link_revoked','link_expired']) {
  test('safe dictionary '+code,()=>{
    const text=invitationMessage({status:'error',reason_code:code,error:'SECRET RAW RESPONSE'});
    assert.ok(text.length>10); assert.ok(!text.includes('SECRET'));
  });
}
test('confirmed refusal differs from unknown even with no safe category',()=>{
  assert.match(invitationMessage({status:'error',reason_code:'future'}),/Причину отказа/);
  assert.match(invitationMessage({status:'uncertain',reason_code:'future'}),/могло быть принято/);
});
test('mixed exact batch keeps known facts and rejects duplicate/foreign entries',()=>{
  const previous=[{email:'a@test',status:'accepted'},{email:'b@test',status:'error',reason_code:'questionnaire_unconfirmed'}];
  const items=exactInvitationItems({items:[{email:'a@test',status:'accepted'},{email:'c@test',status:'accepted'},{email:'c@test',status:'error'},{email:'foreign@test',status:'accepted'}]},['a@test','b@test','c@test'],previous);
  assert.equal(invitationSummary(items),'Приняты сервисом: 1. Не отправлены: 1. Исход уточняется: 1');
  assert.equal(items[1].reason_code,'questionnaire_unconfirmed'); assert.equal(items[2].status,'uncertain');
});
test('common service explanation once and separate lifecycle/link facts',()=>{
  assert.equal(invitationCommonMessage(Array(3).fill({status:'error',reason_code:'mail_not_configured'})).match(/не настроен/g).length,1);
  assert.equal(invitationMessage({status:'queued'}),'Приглашение подготовлено. Отправка ещё не подтверждена');
  for(const code of ['not_created','active','expired','revoked','used','unknown']) assert.ok(invitationLinkMessage(code,'17.11.2026 15:00 GMT+3'));
});

test('raw legacy errors and unknown fields cannot enter row data or stored recovery facts',()=>{
  const [value]=exactInvitationItems({items:[{email:'a@test',status:'error',error:'SECRET KEY',token:'TOKEN',reason_code:'SECRET_CODE',reason_params:{secret:'PRIVATE'}}]},['a@test']);
  assert.ok(!JSON.stringify(value).includes('SECRET')); assert.ok(!JSON.stringify(value).includes('TOKEN'));
  assert.match(invitationMessage(value),/Причину отказа/);
});

test('no attempt is separate from uncertainty',()=>{
  assert.equal(invitationMessage({delivery_status:'not_sent'}),'Письмо не отправлено');
});

test('owner-approved matrix is an independent exact text oracle',async()=>{
  const fs=await import('node:fs/promises');
  const source=await fs.readFile('docs/evc/tasks/p4k-postw02-qa-02/Invitation_Behaviors_Draft.md','utf8');
  const rows=new Map(source.split('\n').filter(line=>line.startsWith('|')).map(line=>{
    const parts=line.split('|');return [parts[1]?.trim(),parts[3]?.trim().replace(/^«|»$/g,'')];
  }));
  const cases=[
    ['invalid_email','Некорректный email','error'],['invalid_request','Не хватает ID операции / невалидный запрос','error'],
    ['session_expired','Сессия истекла','error'],['permission_denied','Нет полномочий на организацию','error'],
    ['questionnaire_unconfirmed','Подтверждённых сведений нет','error'],['questionnaire_incomplete','Обязательные сведения неполны','error'],
    ['organization_unsupported','Тип организации пока не поддержан этим путём','error'],['organization_changed','Сведения изменились между проверками','error'],
    ['member_unavailable','Участник недоступен для приглашения','error'],['access_changed','Организация/доступ изменились до transport','error'],
    ['permission_changed','Права отправителя отозваны до transport','error'],['mail_not_configured','Сервис отправки не настроен','error'],
    ['provider_rejected','Почтовый сервис явно отклонил запрос','error'],['provider_limit','Временный лимит отправки','error'],
    ['queued','Сохранено, но приём сервисом ещё не подтверждён','queued'],['accepted','Письмо принято почтовым сервисом','accepted'],
    ['delivery_unknown','Потерян ответ сервера/timeout/сеть/5xx','uncertain'],['sending','Отправка была начата другим запросом','uncertain'],
    ['context_changed','После transport изменились права/участник/ссылка','uncertain'],['operation_not_found','Readback не находит запись','uncertain'],
    ['failed_unclassified','Подтверждённый отказ, безопасная категория неизвестна','error'],['operation_mismatch','ID принадлежит другой операции/оценке/адресату','error'],
  ];
  for(const [reason_code,name,status]of cases)assert.equal(invitationMessage({reason_code,status}),rows.get(name),name);
});

test('a contradictory operation or invitation identity cannot confirm this command',()=>{
  assert.equal(exactInvitationItems({items:[{email:'a@test',status:'accepted',operation_id:'foreign'}]},['a@test'],[],'owned')[0].status,'uncertain');
  assert.equal(exactInvitationItems({items:[{email:'a@test',status:'accepted',invitation_id:2}]},['a@test'],[{email:'a@test',status:'uncertain',invitation_id:1}],'owned')[0].status,'uncertain');
});

test('a receipt with a foreign recipient cannot establish new batch facts',()=>{
  const response={items:[{email:'a@test',status:'accepted'},{email:'foreign@test',status:'accepted'}]};
  assert.equal(exactInvitationItems(response,['a@test'])[0].status,'uncertain');
  const saved={email:'a@test',status:'error',reason_code:'provider_recipient'};
  assert.deepEqual(exactInvitationItems(response,['a@test'],[saved]),[saved]);
  const partial=exactInvitationItems({items:[{email:'a@test',status:'accepted'}]},['a@test','b@test']);
  assert.deepEqual(partial.map(item=>item.status),['accepted','uncertain']);
});
