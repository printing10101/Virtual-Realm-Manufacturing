"""Verify BudgetManager thread safety fix."""
import os, sys, tempfile, threading, time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "python"))

from app.core.budget import BudgetManager, BudgetLimit, BudgetLevel, ResourceType

with tempfile.TemporaryDirectory() as tmpdir:
    db = os.path.join(tmpdir, "budget.db")
    mgr = BudgetManager(db_path=db)
    
    assert hasattr(mgr, '_lock'), "Missing _lock attribute"
    assert isinstance(mgr._lock, type(threading.RLock())), "_lock is not RLock"
    
    errors = []
    
    def concurrent_set(i):
        try:
            mgr.set_budget_limit(BudgetLimit(
                resource_type=list(ResourceType)[i % len(ResourceType)],
                limit_value=float(i * 100),
                budget_level=BudgetLevel.AGENT,
                scope_id=f"agent_{i}",
            ))
        except Exception as e:
            errors.append(str(e))
    
    threads = [threading.Thread(target=concurrent_set, args=(i,)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    if errors:
        print(f"FAIL: {len(errors)} errors: {errors[:3]}")
        sys.exit(1)
    
    notifs = mgr.get_notifications(limit=100)
    print(f"PASS: 20 concurrent writes, lock type={type(mgr._lock).__name__}, notifications={len(notifs)}")
    mgr.close()
