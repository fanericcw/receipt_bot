import pytest
import discord
from firebase_admin import db
from db_ops import add_to_ledger\

@pytest.fixture
def setup_db_ref(mocker):
    mock_ref_instance = mocker.Mock(spec=db.Reference)
    mock_get_ref = mocker.patch("db_ops.db.reference", return_value=mock_ref_instance)
    return mock_ref_instance, mock_get_ref

@pytest.fixture
def setup_discord(mocker):
    mock_guild = mocker.Mock(spec=discord.Guild)
    mock_guild.id = 123456789

    mock_creditor = mocker.Mock(spec=discord.User)
    mock_creditor.id = 428651069

    mock_debtor = mocker.Mock(spec=discord.User)
    mock_debtor.id = 224964951
    return mock_guild, mock_creditor, mock_debtor


@pytest.mark.asyncio
async def test_add_to_empty_ledger(setup_db_ref, setup_discord):
    mock_ref_instance, mock_get_ref = setup_db_ref
    mock_guild, mock_creditor, mock_debtor = setup_discord

    # Empty db
    mock_ref_instance.get.return_value = []

    await add_to_ledger(67023819087, 0, 14.99, mock_guild, mock_debtor, mock_creditor)

    mock_get_ref.assert_called_once_with(f'/{mock_guild.id}/{mock_debtor.id}/{mock_creditor.id}/67023819087')
    mock_ref_instance.get.assert_called_once()
    mock_ref_instance.set.assert_called_once_with([{
        'item': 0,
        'price': 14.99
    }])

@pytest.mark.asyncio
async def test_add_to_filled_ledger(setup_db_ref, setup_discord):
    mock_ref_instance, mock_get_ref = setup_db_ref
    mock_guild, mock_creditor, mock_debtor = setup_discord

    mock_ref_instance.get.return_value = [{'item': 0, 'price': 18.99}]

    await add_to_ledger(67023819087, 1, 6.89, mock_guild, mock_debtor, mock_creditor)

    mock_get_ref.assert_called_once_with(f'/{mock_guild.id}/{mock_debtor.id}/{mock_creditor.id}/67023819087')
    mock_ref_instance.get.assert_called_once()
    mock_ref_instance.set.assert_called_once_with([
        { 'item': 0, 'price': 18.99 },
        { 'item': 1, 'price': 6.89 }
    ])
