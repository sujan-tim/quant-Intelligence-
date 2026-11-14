"""Local paper ledger. Orders are simulations at the last stored daily close."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Asset, PaperAccount, PaperOrder, PriceBar

STARTING_CASH = Decimal("100000.00")
CENT = Decimal("0.01")
PRICE_UNIT = Decimal("0.0001")


class PaperTradeError(ValueError):
    pass


def _latest_bar(session: Session, asset_id: int) -> PriceBar | None:
    return session.scalar(
        select(PriceBar)
        .where(PriceBar.asset_id == asset_id)
        .order_by(PriceBar.date.desc())
        .limit(1)
    )


def _positions(session: Session) -> dict[int, int]:
    quantities: dict[int, int] = {}
    for order in session.scalars(select(PaperOrder).where(PaperOrder.account_id == 1)):
        direction = 1 if order.side == "buy" else -1
        quantities[order.asset_id] = quantities.get(order.asset_id, 0) + direction * order.quantity
    return {asset_id: quantity for asset_id, quantity in quantities.items() if quantity != 0}


def portfolio(session: Session) -> dict:
    account = session.get(PaperAccount, 1)
    cash = account.cash if account is not None else STARTING_CASH
    positions = []
    market_value = Decimal("0.00")
    for asset_id, quantity in _positions(session).items():
        asset = session.get(Asset, asset_id)
        latest = _latest_bar(session, asset_id)
        if asset is None or latest is None:
            continue
        price = Decimal(str(latest.close)).quantize(PRICE_UNIT)
        value = (price * quantity).quantize(CENT)
        market_value += value
        positions.append(
            {
                "symbol": asset.symbol,
                "quantity": quantity,
                "last_price": float(price),
                "price_date": latest.date,
                "source": asset.source,
                "market_value": float(value),
            }
        )
    positions.sort(key=lambda item: item["symbol"])
    orders = []
    for order in session.scalars(select(PaperOrder).order_by(PaperOrder.id.desc()).limit(50)):
        asset = session.get(Asset, order.asset_id)
        orders.append(
            {
                "id": order.id,
                "symbol": asset.symbol if asset else "UNKNOWN",
                "side": order.side,
                "quantity": order.quantity,
                "execution_price": float(order.execution_price),
                "price_date": order.price_date,
                "source": order.source,
                "created_at": order.created_at,
            }
        )
    return {
        "mode": "paper",
        "execution_rule": "Simulated at last stored daily close; no real broker order",
        "starting_cash": float(STARTING_CASH),
        "cash": float(cash),
        "market_value": float(market_value),
        "equity": float(cash + market_value),
        "positions": positions,
        "orders": orders,
    }


def place_order(session: Session, symbol: str, side: str, quantity: int) -> dict:
    if side not in {"buy", "sell"} or quantity <= 0:
        raise PaperTradeError("Use buy or sell and a positive whole-share quantity")
    asset = session.scalar(select(Asset).where(Asset.symbol == symbol.upper()))
    if asset is None:
        raise PaperTradeError("Load price data for this symbol first")
    latest = _latest_bar(session, asset.id)
    if latest is None or latest.close <= 0:
        raise PaperTradeError("No valid stored closing price for this symbol")
    account = session.scalar(select(PaperAccount).where(PaperAccount.id == 1).with_for_update())
    if account is None:
        account = PaperAccount(id=1, starting_cash=STARTING_CASH, cash=STARTING_CASH)
        session.add(account)
        session.flush()
    price = Decimal(str(latest.close)).quantize(PRICE_UNIT)
    amount = (price * quantity).quantize(CENT)
    if side == "buy" and amount > account.cash:
        raise PaperTradeError("Insufficient paper cash")
    if side == "sell" and quantity > _positions(session).get(asset.id, 0):
        raise PaperTradeError("Insufficient paper shares")
    account.cash += -amount if side == "buy" else amount
    order = PaperOrder(
        account_id=account.id,
        asset_id=asset.id,
        side=side,
        quantity=quantity,
        execution_price=price,
        price_date=latest.date,
        source=asset.source,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    return {
        "id": order.id,
        "mode": "paper",
        "symbol": asset.symbol,
        "side": side,
        "quantity": quantity,
        "execution_price": float(price),
        "price_date": latest.date,
        "source": asset.source,
        "cash_after": float(account.cash),
    }
