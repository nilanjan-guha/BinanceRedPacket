//+------------------------------------------------------------------+
//|                                STEEV_XAUUSD_20Dollar_Grid.mq5    |
//|                        $20 LADDER GRID BOT - XAUUSD M1           |
//|                                  Copyright 2026, Nilanjan Guha   |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2026, Nilanjan Guha"
#property link      "https://www.mql5.com"
#property version   "103.00"
#property strict

// Include standard trade library
#include <Trade\Trade.mqh>

//--- Input Parameters
input group "=== Custom Balance Tier Lot Settings ==="
input double   InpTier1_Balance            = 20.00;    // Tier 1 Balance (< $50)
input double   InpTier1_Lot                = 0.02;     // Tier 1 Lot Size (0.02)
input double   InpTier2_Balance            = 50.00;    // Tier 2 Balance ($50 - $79.99)
input double   InpTier2_Lot                = 0.03;     // Tier 2 Lot Size (0.03)
input double   InpTier3_Balance            = 80.00;    // Tier 3 Balance ($80+)
input double   InpTier3_Lot                = 0.04;     // Tier 3 Lot Size (0.04)
input double   InpStepAbove80USD           = 30.00;    // Step above $80 to add +0.01 lot ($30)
input double   InpMaxLot                   = 1.00;     // Maximum Lot Cap

input group "=== Grid Entry Settings ==="
input int      InpGridOrdersPerSide        = 5;        // Number of Stop Orders per side (5 Buy Stop, 5 Sell Stop)
input double   InpGridDistancePrice        = 0.50;     // Grid Distance in Price ($0.50 between orders)
input double   InpOrderTPUSD               = 1.00;     // Take Profit per trade (+$1.00)
input double   InpOrderSLUSD               = 0.50;     // Stop Loss per trade (-$0.50)

input group "=== System / Broker Settings ==="
input int      InpMaxSpreadPoints          = 400;      // Max allowed spread in points
input ulong    InpMagicNumber              = 77720;    // Unique Magic Number

//--- Global Variables
CTrade         ExtTrade;
datetime       g_lastDayTracked            = 0;
double         g_dayStartBalance           = 0.0;
datetime       g_lastGridPlacementTime     = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   ExtTrade.SetExpertMagicNumber(InpMagicNumber);
   ExtTrade.SetMarginMode();
   ExtTrade.SetTypeFillingBySymbol(_Symbol);

   g_lastDayTracked = 0;
   g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);

   Print("=== $20 LADDER GRID BOT INITIALIZED (v103.00 - Custom Tier Lots) ===");
   PrintFormat("Account Balance: $%.2f | Magic: %d | TP: $%.2f | SL: $%.2f", 
               g_dayStartBalance, InpMagicNumber, InpOrderTPUSD, InpOrderSLUSD);

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Comment("");
}

//+------------------------------------------------------------------+
//| Calculate Dynamic Ladder Lot Size based on Current Balance       |
//| Start at $20 = 0.02 Lot.                                         |
//| $50 = 0.03 Lot.                                                  |
//| $80 = 0.04 Lot (or 0.03 if desired).                             |
//| Decreases dynamically if balance drops below tier threshold.     |
//+------------------------------------------------------------------+
double CalculateLadderLot()
{
   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dynamicLot = InpTier1_Lot; // Default start = 0.02

   if(balance >= InpTier3_Balance) // $80 or above
   {
      int extraTiers = (int)MathFloor((balance - InpTier3_Balance) / InpStepAbove80USD);
      dynamicLot = InpTier3_Lot + (extraTiers * 0.01);
   }
   else if(balance >= InpTier2_Balance) // $50 to $79.99
   {
      dynamicLot = InpTier2_Lot; // 0.03
   }
   else // Under $50 (e.g. $20 - $49.99)
   {
      dynamicLot = InpTier1_Lot; // 0.02
   }

   if(dynamicLot > InpMaxLot) dynamicLot = InpMaxLot;
   if(dynamicLot < 0.01)      dynamicLot = 0.01;

   // Align with broker lot step & min/max lot
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   if(lotStep > 0)
      dynamicLot = MathFloor(dynamicLot / lotStep) * lotStep;

   if(dynamicLot < minLot) dynamicLot = minLot;
   if(dynamicLot > maxLot) dynamicLot = maxLot;

   return NormalizeDouble(dynamicLot, 2);
}

//+------------------------------------------------------------------+
//| Track Daily Stats for Display                                    |
//+------------------------------------------------------------------+
void CheckDailyTracker()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime todayMidnight = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(g_lastDayTracked != todayMidnight)
   {
      g_lastDayTracked = todayMidnight;
      g_dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   }
}

//+------------------------------------------------------------------+
//| Delete all pending Buy Stop & Sell Stop orders                   |
//+------------------------------------------------------------------+
void DeleteAllPendingOrders()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0)
      {
         if(OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagicNumber)
         {
            ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
            if(type == ORDER_TYPE_BUY_STOP || type == ORDER_TYPE_SELL_STOP ||
               type == ORDER_TYPE_BUY_LIMIT || type == ORDER_TYPE_SELL_LIMIT)
            {
               ExtTrade.OrderDelete(ticket);
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Calculate Price delta corresponding to Target USD Profit/Loss   |
//+------------------------------------------------------------------+
double CalculatePriceOffsetForUSD(double targetUSD, double lot)
{
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);

   if(tickValue <= 0 || tickSize <= 0)
   {
      // Fallback for standard 100oz XAUUSD: 0.01 lot = $1.00 per $1.00 price move
      return (targetUSD / (lot * 100.0));
   }

   // Formula: profit = (deltaPrice / tickSize) * tickValue * (lot / minLot)
   double deltaPrice = (targetUSD * tickSize) / (tickValue * lot);
   return deltaPrice;
}

//+------------------------------------------------------------------+
//| Place the 5 Buy Stops and 5 Sell Stops Ladder Grid               |
//+------------------------------------------------------------------+
void PlaceLadderGrid()
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double currentLot = CalculateLadderLot();

   // Price distance offset for +$1.00 TP and -$0.50 SL at current lot size
   double tpOffset = CalculatePriceOffsetForUSD(InpOrderTPUSD, currentLot);
   double slOffset = CalculatePriceOffsetForUSD(InpOrderSLUSD, currentLot);

   // Ensure minimum distance from ask/bid (stops level)
   long stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minStopDistance = stopsLevel * SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double baseDistance = InpGridDistancePrice;
   if(baseDistance < minStopDistance) baseDistance = minStopDistance + 0.10;

   // 1. Place 5 BUY STOPs above Current Price
   for(int i = 1; i <= InpGridOrdersPerSide; i++)
   {
      double orderPrice = NormalizeDouble(ask + (i * baseDistance), digits);
      double tpPrice    = NormalizeDouble(orderPrice + tpOffset, digits);
      double slPrice    = NormalizeDouble(orderPrice - slOffset, digits);

      ExtTrade.BuyStop(currentLot, orderPrice, _Symbol, slPrice, tpPrice, ORDER_TIME_GTC, 0, "$20 Ladder BuyStop");
   }

   // 2. Place 5 SELL STOPs below Current Price
   for(int i = 1; i <= InpGridOrdersPerSide; i++)
   {
      double orderPrice = NormalizeDouble(bid - (i * baseDistance), digits);
      double tpPrice    = NormalizeDouble(orderPrice - tpOffset, digits);
      double slPrice    = NormalizeDouble(orderPrice + slOffset, digits);

      ExtTrade.SellStop(currentLot, orderPrice, _Symbol, slPrice, tpPrice, ORDER_TIME_GTC, 0, "$20 Ladder SellStop");
   }

   g_lastGridPlacementTime = TimeCurrent();
   PrintFormat("Ladder Grid Placed: 5 Buy Stops & 5 Sell Stops @ %.2f Lot | Dist: $%.2f | TP: +$%.2f | SL: -$%.2f",
               currentLot, baseDistance, InpOrderTPUSD, InpOrderSLUSD);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   CheckDailyTracker();

   double currentBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   double dayProfit = currentBalance - g_dayStartBalance;

   // 1. Count Active Positions and Pending Orders
   int activeBuyPositions = 0, activeSellPositions = 0;
   int pendingBuyStops = 0, pendingSellStops = 0;
   double totalFloatingProfit = 0.0;

   for(int i = 0; i < PositionsTotal(); i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagicNumber)
      {
         totalFloatingProfit += PositionGetDouble(POSITION_PROFIT);
         ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         if(type == POSITION_TYPE_BUY) activeBuyPositions++;
         if(type == POSITION_TYPE_SELL) activeSellPositions++;
      }
   }

   for(int i = 0; i < OrdersTotal(); i++)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagicNumber)
      {
         ENUM_ORDER_TYPE type = (ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE);
         if(type == ORDER_TYPE_BUY_STOP) pendingBuyStops++;
         if(type == ORDER_TYPE_SELL_STOP) pendingSellStops++;
      }
   }

   int totalPositions = activeBuyPositions + activeSellPositions;
   int totalPending   = pendingBuyStops + pendingSellStops;

   // 2. Check Spread
   long currentSpread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   bool spreadOk = (currentSpread <= InpMaxSpreadPoints);

   // 3. Grid Management: Continuous Loop
   // If no positions are open and no pending orders exist -> Place fresh ladder grid
   if(totalPositions == 0 && totalPending == 0 && spreadOk)
   {
      PlaceLadderGrid();
   }

   // If all positions finished (closed via TP or SL) but old orphaned pending orders remain -> Clean up and refresh
   if(totalPositions == 0 && totalPending > 0 && (TimeCurrent() - g_lastGridPlacementTime > 60))
   {
      DeleteAllPendingOrders();
   }

   // 4. On-Screen Live Dashboard
   double activeLadderLot = CalculateLadderLot();
   string statusStr = "RUNNING (Continuous Hunting)";
   if(!spreadOk) statusStr = StringFormat("WAITING (Spread %d > %d pts)", currentSpread, InpMaxSpreadPoints);

   Comment(StringFormat(
      "==========================================================\n"
      "   $20 LADDER GRID BOT - CONTINUOUS (v103.00)            \n"
      "==========================================================\n"
      "Account Balance       : $%.2f\n"
      "Active Ladder Lot     : %.2f Lot (Auto-Adjusts by Balance)\n"
      "Today's Net Profit    : $%.2f\n"
      "Open Positions        : %d (Buy: %d, Sell: %d)\n"
      "Active Pending Orders : %d (5 Buy Stop, 5 Sell Stop)\n"
      "Floating Profit/Loss  : $%.2f\n"
      "Spread                : %d points\n"
      "Target TP per Trade   : +$%.2f\n"
      "Stop Loss per Trade   : -$%.2f\n"
      "Execution Status      : %s\n"
      "==========================================================\n"
      "BALANCE TIERS:\n"
      "  * Start ($20 - $49.99) -> 0.02 Lot\n"
      "  * $50 - $79.99         -> 0.03 Lot\n"
      "  * $80+                 -> 0.04 Lot (+0.01 per $30 step)\n"
      "  * If balance drops, lot scales DOWN automatically\n"
      "==========================================================",
      currentBalance,
      activeLadderLot,
      dayProfit,
      totalPositions, activeBuyPositions, activeSellPositions,
      totalPending,
      totalFloatingProfit,
      currentSpread,
      InpOrderTPUSD,
      InpOrderSLUSD,
      statusStr
   ));
}
//+------------------------------------------------------------------+
