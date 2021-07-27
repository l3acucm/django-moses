import json

from django.contrib.auth.models import Group
from django.urls import reverse
from django.test import Client
from django.contrib.auth import get_user_model

from rest_framework.test import force_authenticate, APIRequestFactory

from djoser.views import UserViewSet

from sinbad.logistics.views import StageAchievementViewSet
from sinbad.catalogue.views import AssetTypeViewSet, AssetViewSet, MenuSectionViewSet, MenuSectionEntryViewSet
from sinbad.company.views import CompanyViewSet, StaffInviteViewSet, TransactionNodeTag, CustomerStatusViewSet, \
    StaffRoleViewSet
from sinbad.logistics.models import Transaction, TransactionNode, TransactionTag
from sinbad.logistics.models.pipeline import StageAchievement, Pipeline
from sinbad.logistics.views import TransactionTagViewSet, TransactionViewSet, TransactionNodeViewSet, \
    TransactionNodeTagViewSet, PipelineViewSet
from sinbad.catalogue.models import Asset, AssetType, MenuSection, MenuSectionEntry
from sinbad.company.models import Company, CustomerStatus
from sinbad.trade.models import Order, Offer, OrderReturn
from sinbad.trade.views import OfferViewSet, OrderViewSet, OrderReturnViewSet

client = Client()
drf_request_factory = APIRequestFactory()

create_node_view = TransactionNodeViewSet.as_view({'post': 'create'})
create_offer_view = OfferViewSet.as_view({'post': 'create'})
create_company_view = CompanyViewSet.as_view({'post': 'create'})
create_user_view = UserViewSet.as_view({'post': 'create'})
create_asset_view = AssetViewSet.as_view({'post': 'create'})
create_asset_type_view = AssetTypeViewSet.as_view({'post': 'create'})
edit_company_view = CompanyViewSet.as_view({'patch': 'partial_update'})
create_transaction_tag_view = TransactionTagViewSet.as_view({'post': 'create'})
edit_income_transaction_tag_view = TransactionTagViewSet.as_view({'patch': 'partial_update'})
list_income_transaction_tags_view = TransactionTagViewSet.as_view({'get': 'list'})
delete_income_transaction_tag_view = TransactionTagViewSet.as_view({'delete': 'destroy'})
get_incomes_view = TransactionViewSet.as_view({'get': 'list'})
create_income_view = TransactionViewSet.as_view({'post': 'create'})
create_invite_view = StaffInviteViewSet.as_view({'post': 'create'})
create_node_tag_view = TransactionNodeTagViewSet.as_view({'post': 'create'})
create_pipeline_view = PipelineViewSet.as_view({'post': 'create'})
confirm_invite_view = StaffInviteViewSet.as_view({'put': 'update'})
create_menu_section_view = MenuSectionViewSet.as_view({'post': 'create'})
create_menu_section_entry_view = MenuSectionEntryViewSet.as_view({'post': 'create'})
delete_invite_view = StaffInviteViewSet.as_view({'delete': 'destroy'})
create_staff_role_view = StaffRoleViewSet.as_view({'post': 'create'})
update_staff_role_view = StaffRoleViewSet.as_view({'patch': 'partial_update'})
update_node_view = TransactionNodeViewSet.as_view({'patch': 'partial_update'})
create_transaction_view = TransactionViewSet.as_view({'post': 'create'})
create_order_view = OrderViewSet.as_view({'post': 'create'})
create_order_return_view = OrderReturnViewSet.as_view({'post': 'create'})
create_stage_achievement_view = StageAchievementViewSet.as_view({'post': 'create'})
confirm_stage_achievement_view = StageAchievementViewSet.as_view({'put': 'update'})
create_customer_status_view = CustomerStatusViewSet.as_view({'post': 'create'})
update_customer_status_view = CustomerStatusViewSet.as_view({'patch': 'partial_update'})


def create_user(phone_number, password, name, email):
    request = drf_request_factory.post('/api/accounts/users/',
                                       json.dumps({
                                           'username': phone_number,
                                           'phone_number': phone_number,
                                           'password': password,
                                           'first_name': name,
                                           'email': email}),
                                       content_type='application/json')

    response = create_user_view(request)
    user = get_user_model().objects.last() if response.status_code == 201 else None
    return user, response


def create_offer(user, income_node_id, outcome_node_id, income_entries, outcome_entries):
    request = drf_request_factory.post(reverse('sinbad:trade:Order-list'),
                                       json.dumps({'income_node': income_node_id,
                                                   'outcome_node': outcome_node_id,
                                                   'income_entries_data': income_entries,
                                                   'outcome_entries_data': outcome_entries}),
                                       content_type='application/json')

    force_authenticate(request, user=user)
    response = create_offer_view(request)
    offer = Offer.objects.last() if response.status_code == 201 else None
    return offer, response


def create_role(user, company, role_name):
    request = drf_request_factory.post(
        reverse('sinbad:company:StaffRole-list'),
        json.dumps({'company_id': company.id, 'name': role_name}),
        content_type='application/json')
    force_authenticate(request, user=user)
    response = create_staff_role_view(request)
    role = Group.objects.get(name=f"{company.id}.roles.{role_name}") if response.status_code == 201 else None
    return role, response


def assign_user_to_node(user, node, user_to_assign_to):
    request = drf_request_factory.patch(
        reverse('sinbad:logistics:TransactionNode-detail', kwargs={'pk': node.id}),
        json.dumps({'user_to_assign_to': user_to_assign_to}),
        content_type='application/json')
    force_authenticate(request, user=user)
    response = update_node_view(request, pk=node.id)
    return TransactionNode.objects.get(id=node.id), response


def create_order(user, offer, amount, income_node, outcome_node):
    request = drf_request_factory.post(
        reverse('sinbad:trade:Order-list'),
        json.dumps(
            {'income_node': income_node.id,
             'outcome_node': outcome_node.id,
             'order_entries': [{
                 'amount': amount,
                 'offer_id': offer.id,
             }]}),
        content_type='application/json')
    force_authenticate(request, user=user)
    response = create_order_view(request)
    order = Order.objects.last() if response.status_code == 201 else None
    return order, response


def create_order_return(user, order_entry, amount):
    request = drf_request_factory.post(
        reverse('sinbad:trade:OrderReturn-list'),
        json.dumps({'amount': amount, 'order_entry': order_entry.id}),
        content_type='application/json')
    force_authenticate(request, user=user)
    response = create_order_return_view(request)
    order = OrderReturn.objects.last() if response.status_code == 201 else None
    return order, response


def assign_achievement_perm(user, role, stage):
    request = drf_request_factory.patch(
        reverse('sinbad:company:StaffRole-detail', kwargs={'pk': role.id}),
        json.dumps({'permission_manipulations': [
            {
                'action': 'assign',
                'permission': 'apply_stage',
                'instance': stage.id
            }
        ]}),
        content_type='application/json')
    force_authenticate(request, user=user)
    return update_staff_role_view(request, pk=role.id)


def assign_order_perm(user, role, outcome_node_tag):
    request = drf_request_factory.patch(
        reverse('sinbad:company:StaffRole-detail', kwargs={'pk': role.id}),
        json.dumps({'permission_manipulations': [
            {
                'action': 'assign',
                'permission': 'create_orders',
                'instance': outcome_node_tag.id
            }
        ]}),
        content_type='application/json')
    force_authenticate(request, user=user)
    return update_staff_role_view(request, pk=role.id)


def invite_staff(user, role, member):
    request = drf_request_factory.post(
        reverse('sinbad:company:StaffInvite-list'),
        json.dumps({'role': role.id, 'member': member.username}),
        content_type='application/json')
    force_authenticate(request, user=user)
    return create_invite_view(request)


def confirm_invite(user, invite):
    request = drf_request_factory.put(
        reverse('sinbad:company:StaffInvite-detail', kwargs={'pk': invite.id}),
        json.dumps({}),
        content_type='application/json')
    force_authenticate(request, user=user)
    return confirm_invite_view(request, pk=invite.id)


def decline_invite(user, invite, company_id=None):
    url = reverse('sinbad:company:StaffInvite-detail', kwargs={'pk': invite.id})
    if company_id is not None:
        url += f'?company={company_id}'
    request = drf_request_factory.delete(
        url,
        json.dumps({}),
        content_type='application/json')
    force_authenticate(request, user=user)
    return delete_invite_view(request, pk=invite.id)


def create_transaction_tag(user, company, name):
    request = drf_request_factory.post(reverse('sinbad:company:Company-list') + '?language=ru',
                                       json.dumps({'name': name,
                                                   'company': company}),
                                       content_type='application/json')

    force_authenticate(request, user=user)
    response = create_transaction_tag_view(request)
    tag = TransactionTag.objects.last() if response.status_code == 201 else None
    return tag, response


def create_company(user, name):
    request = drf_request_factory.post(reverse('sinbad:company:Company-list') + '?language=ru',
                                       json.dumps({'name': name}),
                                       content_type='application/json')

    force_authenticate(request, user=user)
    response = create_company_view(request)
    company = Company.objects.last() if response.status_code == 201 else None
    return company, response


def create_node(user, company, internal_id, field_values, tags, income_transaction_tags,
                outcome_transaction_tags):
    request = drf_request_factory.post(reverse('sinbad:logistics:TransactionNode-list'),
                                       json.dumps({'company': company.id,
                                                   'internal_id': internal_id,
                                                   'field_values': field_values,
                                                   'tags': tags,
                                                   'income_transaction_tag_ids': income_transaction_tags,
                                                   'outcome_transaction_tag_ids': outcome_transaction_tags}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_node_view(request)
    node = TransactionNode.objects.last() if response.status_code == 201 else None
    return node, response


def update_node(user, node, data):
    request = drf_request_factory.patch(reverse('sinbad:logistics:TransactionNode-detail', kwargs={"pk": node.id}),
                                        json.dumps(data),
                                        content_type='application/json')
    force_authenticate(request, user=user)
    response = update_node_view(request, pk=node.id)
    node = TransactionNode.objects.get(id=node.id) if response.status_code == 200 else node
    return node, response


def create_customer_status(user, data):
    request = drf_request_factory.post(reverse('sinbad:company:CustomerStatus-list'),
                                       json.dumps(data),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_customer_status_view(request)
    customer_status = CustomerStatus.objects.last() if response.status_code == 201 else None
    return customer_status, response


def update_customer_status(user, customer_status, data):
    request = drf_request_factory.patch(reverse('sinbad:company:CustomerStatus-detail', kwargs={"pk": customer_status.id}),
                                        json.dumps(data),
                                        content_type='application/json')
    force_authenticate(request, user=user)
    response = update_customer_status_view(request, pk=customer_status.id)
    customer_status = CustomerStatus.objects.get(
        id=customer_status.id) if response.status_code == 200 else customer_status
    return customer_status, response


def create_pipeline(user, company, name, stages):
    request = drf_request_factory.post(reverse('sinbad:catalogue:MenuSection-list'),
                                       json.dumps({'company': company.id,
                                                   'stages': stages,
                                                   'name': name}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_pipeline_view(request)
    pipeline = Pipeline.objects.last() if response.status_code == 201 else None
    return pipeline, response


def create_menu_section(user, company, parent_id, name):
    request = drf_request_factory.post(reverse('sinbad:catalogue:MenuSection-list'),
                                       json.dumps({'company': company.id,
                                                   'parent': parent_id,
                                                   'name': name}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_menu_section_view(request)
    menu_section = MenuSection.objects.last() if response.status_code == 201 else None
    return menu_section, response


def create_menu_section_entry(user, menu_section, asset):
    request = drf_request_factory.post(reverse('sinbad:catalogue:MenuSectionEntry-list'),
                                       json.dumps({'menu_section': menu_section.id,
                                                   'asset': asset.id}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_menu_section_entry_view(request)
    menu_section_entry = MenuSectionEntry.objects.last() if response.status_code == 201 else None
    return menu_section_entry, response


def create_asset_type(user, company_id, verbose_name, fields):
    request = drf_request_factory.post(reverse('sinbad:catalogue:AssetType-list'),
                                       json.dumps({'company': company_id,
                                                   'verbose_name': verbose_name,
                                                   'fields_to_create': fields}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_asset_type_view(request)
    asset_type = AssetType.objects.last() if response.status_code == 201 else None
    return asset_type, response


def create_asset(user, asset_type_id, barcode, verbose_name, field_values):
    request = drf_request_factory.post(reverse('sinbad:catalogue:Asset-list'),
                                       json.dumps({'barcode': barcode,
                                                   'asset_type': asset_type_id,
                                                   'verbose_name': verbose_name,
                                                   'field_values': field_values}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_asset_view(request)
    asset = Asset.objects.last() if response.status_code == 201 else None
    return asset, response


def create_node_tag(user, company, internal_id, fields):
    request = drf_request_factory.post(reverse('sinbad:catalogue:Asset-list'),
                                       json.dumps({'company': company.id,
                                                   'name': internal_id,
                                                   'fields_to_create': fields}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_node_tag_view(request)
    tag = TransactionNodeTag.objects.last() if response.status_code == 201 else None
    return tag, response


def create_transaction(user, source_node, destination_node, entries, tag_ids):
    request = drf_request_factory.post(reverse('sinbad:logistics:Transaction-list'),
                                       json.dumps({'source': source_node.id if source_node else None,
                                                   'destination': destination_node.id if destination_node else None,
                                                   'entries': entries,
                                                   'tags': tag_ids}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_transaction_view(request)
    transaction = Transaction.objects.last() if response.status_code == 201 else None
    return transaction, response


def compensate_return(user, order, entries):
    request = drf_request_factory.post(reverse('sinbad:logistics:Transaction-list'),
                                       json.dumps({'order_to_compensate_for': order.id,
                                                   'entries': entries,
                                                   'tags': []}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_transaction_view(request)
    transaction = Transaction.objects.last() if response.status_code == 201 else None
    return transaction, response


def create_order_entry_transaction(user, order_entry, tag_ids):
    request = drf_request_factory.post(reverse('sinbad:logistics:Transaction-list'),
                                       json.dumps({'order_entry': order_entry.id,
                                                   'tags': tag_ids}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_transaction_view(request)
    transaction = Transaction.objects.last() if response.status_code == 201 else None
    return transaction, response


def create_order_payment(user, order, entries, tag_ids):
    request = drf_request_factory.post(reverse('sinbad:logistics:Transaction-list'),
                                       json.dumps({'order_to_pay': order.id,
                                                   'entries': entries,
                                                   'tags': tag_ids}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_transaction_view(request)
    transaction = Transaction.objects.last() if response.status_code == 201 else None
    return transaction, response


def achieve_transaction_stage(user, transaction_entry, stage):
    request = drf_request_factory.post(reverse('sinbad:logistics:StageAchievement-list'),
                                       json.dumps({'transaction_entry': transaction_entry.id,
                                                   'stage': stage.id}),
                                       content_type='application/json')
    force_authenticate(request, user=user)
    response = create_stage_achievement_view(request)
    achievement = StageAchievement.objects.last() if response.status_code == 201 else None
    return achievement, response


def attach_achievement_document(user, achievement, file):
    request = drf_request_factory.put(
        reverse('sinbad:logistics:StageAchievement-detail', kwargs={'pk': achievement.pk}),
        {'attachment_0': file},
        format='multipart')
    force_authenticate(request, user=user)
    response = confirm_stage_achievement_view(request, pk=achievement.pk)
    achievement = StageAchievement.objects.get(id=achievement.id)
    return achievement, response


def confirm_achievement(user, achievement):
    request = drf_request_factory.put(
        reverse('sinbad:logistics:StageAchievement-detail', kwargs={"pk": achievement.id}),
        json.dumps({'achievement': achievement.id, 'confirm': True}),
        content_type='application/json')
    force_authenticate(request, user=user)
    response = confirm_stage_achievement_view(request, pk=achievement.id)
    achievement = StageAchievement.objects.get(
        id=achievement.id) if response.status_code == 200 else achievement
    return achievement, response


def create_income_transaction_tag(user, name, company_id):
    request = drf_request_factory.post(
        reverse('sinbad:logistics:TransactionTag-list'),
        json.dumps({'name': name, 'company': company_id}),
        content_type='application/json')
    force_authenticate(request, user=user)
    response = create_transaction_tag_view(request)
    tag = TransactionTag.objects.last() if response.status_code == 201 else None
    return tag, response
