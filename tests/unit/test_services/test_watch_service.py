"""
Unit tests for WatchService.

Tests cover:
- Creating watches
- Getting watches (success + ownership enforcement)
- Listing watches (all vs active only)
- Deactivating watches
- Watch run lifecycle (start, complete, fail)
- Alert creation and listing
- Due watch listing
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.db.models.watch import AlertSeverity, WatchCadence, WatchRunStatus, WatchScopeType, WatchType
from src.services.result_objects import ErrorCode
from src.services.watch_service import WatchService


# ==================== Local Fixtures ====================

@pytest.fixture
def watch_service(mock_db_session):
    return WatchService(db=mock_db_session)


@pytest.fixture
def sample_watch():
    watch = MagicMock()
    watch.id = uuid4()
    watch.account_id = 42
    watch.name = "Test Watch"
    watch.description = "A test watch"
    watch.scope_type = WatchScopeType.portfolio
    watch.scope_ref = "1"
    watch.watch_type = WatchType.portfolio_health
    watch.cadence = WatchCadence.daily
    watch.is_active = True
    watch.created_at = datetime.now(timezone.utc)
    watch.updated_at = None
    watch.last_run_at = None
    watch.last_alert_at = None
    return watch


@pytest.fixture
def sample_watch_run(sample_watch):
    run = MagicMock()
    run.id = uuid4()
    run.watch_id = sample_watch.id
    run.started_at = datetime.now(timezone.utc)
    run.completed_at = None
    run.status = WatchRunStatus.started
    run.summary = None
    run.raw_result_json = None
    run.error_message = None
    return run


@pytest.fixture
def sample_alert(sample_watch):
    alert = MagicMock()
    alert.id = uuid4()
    alert.watch_id = sample_watch.id
    alert.watch_run_id = None
    alert.severity = AlertSeverity.medium
    alert.title = "Test Alert"
    alert.message = "Something needs attention"
    alert.evidence_json = None
    alert.sent_at = None
    alert.suppressed_reason = None
    alert.created_at = datetime.now(timezone.utc)
    return alert


def _mock_scalar_result(value):
    """Return a mock execute result where scalar_one_or_none() returns value."""
    r = MagicMock()
    r.scalar_one_or_none.return_value = value
    return r


def _mock_scalars_result(values):
    """Return a mock execute result where scalars().all() returns values."""
    scalars = MagicMock()
    scalars.all.return_value = values
    r = MagicMock()
    r.scalars.return_value = scalars
    return r


# ==================== Tests ====================

class TestCreateWatch:

    @pytest.mark.asyncio
    async def test_create_watch_success(self, watch_service, mock_db_session):
        mock_db_session.refresh = AsyncMock(return_value=None)

        result = await watch_service.create_watch(
            account_id=42,
            name="My Watch",
            description="A watch",
            scope_type=WatchScopeType.portfolio,
            scope_ref="1",
            watch_type=WatchType.portfolio_health,
            cadence=WatchCadence.daily,
        )

        assert result.success is True
        assert result.watch is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()


class TestGetWatch:

    @pytest.mark.asyncio
    async def test_get_watch_success(self, watch_service, mock_db_session, sample_watch):
        mock_db_session.execute.return_value = _mock_scalar_result(sample_watch)

        result = await watch_service.get_watch(watch_id=sample_watch.id, account_id=42)

        assert result.success is True
        assert result.watch is sample_watch

    @pytest.mark.asyncio
    async def test_get_watch_not_found(self, watch_service, mock_db_session):
        mock_db_session.execute.return_value = _mock_scalar_result(None)

        result = await watch_service.get_watch(watch_id=uuid4(), account_id=42)

        assert result.success is False
        assert result.error_code == ErrorCode.NOT_FOUND

    @pytest.mark.asyncio
    async def test_get_watch_wrong_account_returns_not_accessible(
        self, watch_service, mock_db_session, sample_watch
    ):
        mock_db_session.execute.return_value = _mock_scalar_result(sample_watch)

        result = await watch_service.get_watch(
            watch_id=sample_watch.id,
            account_id=999,  # sample_watch.account_id == 42
        )

        assert result.success is False
        assert result.error_code == ErrorCode.NOT_ACCESSIBLE


class TestListWatches:

    @pytest.mark.asyncio
    async def test_list_watches_all(self, watch_service, mock_db_session, sample_watch):
        mock_db_session.execute.return_value = _mock_scalars_result([sample_watch])

        result = await watch_service.list_watches(account_id=42)

        assert result.success is True
        assert len(result.watches) == 1
        assert result.watches[0] is sample_watch

    @pytest.mark.asyncio
    async def test_list_watches_active_only(self, watch_service, mock_db_session, sample_watch):
        mock_db_session.execute.return_value = _mock_scalars_result([sample_watch])

        result = await watch_service.list_watches(account_id=42, active_only=True)

        assert result.success is True
        assert len(result.watches) == 1

    @pytest.mark.asyncio
    async def test_list_watches_empty(self, watch_service, mock_db_session):
        mock_db_session.execute.return_value = _mock_scalars_result([])

        result = await watch_service.list_watches(account_id=42)

        assert result.success is True
        assert result.watches == []


class TestDeactivateWatch:

    @pytest.mark.asyncio
    async def test_deactivate_watch(self, watch_service, mock_db_session, sample_watch):
        mock_db_session.execute.return_value = _mock_scalar_result(sample_watch)
        mock_db_session.refresh = AsyncMock(return_value=None)

        result = await watch_service.deactivate_watch(
            watch_id=sample_watch.id, account_id=42
        )

        assert result.success is True
        assert sample_watch.is_active is False


class TestStartWatchRun:

    @pytest.mark.asyncio
    async def test_start_watch_run(self, watch_service, mock_db_session, sample_watch):
        mock_db_session.execute.return_value = _mock_scalar_result(sample_watch)
        mock_db_session.refresh = AsyncMock(return_value=None)

        result = await watch_service.start_watch_run(watch_id=sample_watch.id)

        assert result.success is True
        assert result.watch_run is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_watch_run_watch_not_found(self, watch_service, mock_db_session):
        mock_db_session.execute.return_value = _mock_scalar_result(None)

        result = await watch_service.start_watch_run(watch_id=uuid4())

        assert result.success is False
        assert result.error_code == ErrorCode.NOT_FOUND


class TestCompleteWatchRun:

    @pytest.mark.asyncio
    async def test_complete_watch_run(
        self, watch_service, mock_db_session, sample_watch_run
    ):
        mock_db_session.execute.return_value = _mock_scalar_result(sample_watch_run)
        mock_db_session.refresh = AsyncMock(return_value=None)

        result = await watch_service.complete_watch_run(
            run_id=sample_watch_run.id, summary="All good"
        )

        assert result.success is True
        assert sample_watch_run.status == WatchRunStatus.completed
        assert sample_watch_run.summary == "All good"
        assert sample_watch_run.completed_at is not None


class TestFailWatchRun:

    @pytest.mark.asyncio
    async def test_fail_watch_run(self, watch_service, mock_db_session, sample_watch_run):
        mock_db_session.execute.return_value = _mock_scalar_result(sample_watch_run)
        mock_db_session.refresh = AsyncMock(return_value=None)

        result = await watch_service.fail_watch_run(
            run_id=sample_watch_run.id, error_message="Something went wrong"
        )

        assert result.success is True
        assert sample_watch_run.status == WatchRunStatus.failed
        assert sample_watch_run.error_message == "Something went wrong"


class TestCreateAlert:

    @pytest.mark.asyncio
    async def test_create_alert(self, watch_service, mock_db_session, sample_watch):
        # execute is called twice: once for add alert, once for watch lookup
        mock_db_session.execute.return_value = _mock_scalar_result(sample_watch)
        mock_db_session.refresh = AsyncMock(return_value=None)

        result = await watch_service.create_alert(
            watch_id=sample_watch.id,
            watch_run_id=None,
            severity=AlertSeverity.high,
            title="Price Alert",
            message="Price moved significantly",
        )

        assert result.success is True
        assert result.alert is not None
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        assert sample_watch.last_alert_at is not None


class TestListAlerts:

    @pytest.mark.asyncio
    async def test_list_alerts(self, watch_service, mock_db_session, sample_alert):
        mock_db_session.execute.return_value = _mock_scalars_result([sample_alert])

        result = await watch_service.list_alerts(account_id=42)

        assert result.success is True
        assert len(result.alerts) == 1
        assert result.alerts[0] is sample_alert

    @pytest.mark.asyncio
    async def test_list_alerts_empty(self, watch_service, mock_db_session):
        mock_db_session.execute.return_value = _mock_scalars_result([])

        result = await watch_service.list_alerts(account_id=42)

        assert result.success is True
        assert result.alerts == []


class TestListDueWatches:

    @pytest.mark.asyncio
    async def test_list_due_watches_all(self, watch_service, mock_db_session, sample_watch):
        mock_db_session.execute.return_value = _mock_scalars_result([sample_watch])

        result = await watch_service.list_due_watches()

        assert result.success is True
        assert len(result.watches) == 1
        assert result.watches[0] is sample_watch

    @pytest.mark.asyncio
    async def test_list_due_watches_with_cadence_filter(
        self, watch_service, mock_db_session, sample_watch
    ):
        mock_db_session.execute.return_value = _mock_scalars_result([sample_watch])

        result = await watch_service.list_due_watches(cadence=WatchCadence.daily)

        assert result.success is True
        assert len(result.watches) == 1

    @pytest.mark.asyncio
    async def test_list_due_watches_empty(self, watch_service, mock_db_session):
        mock_db_session.execute.return_value = _mock_scalars_result([])

        result = await watch_service.list_due_watches()

        assert result.success is True
        assert result.watches == []
