import React from 'react';
import { Users, CheckCircle2, AlertCircle, Clock, XCircle, ShieldAlert } from 'lucide-react';
import { DashboardStats } from '../types';

interface StatCardsProps {
  stats: DashboardStats | null;
  onFilterSelect?: (status: string) => void;
}

export const StatCards: React.FC<StatCardsProps> = ({ stats, onFilterSelect }) => {
  if (!stats) return null;

  const cards = [
    {
      label: 'Total Enrolled',
      value: stats.total_enrolled,
      icon: Users,
      color: 'text-slate-700',
      bg: 'bg-slate-50',
      border: 'border-slate-200',
      filterKey: 'all'
    },
    {
      label: 'Confirmed Present',
      value: stats.confirmed_count,
      icon: CheckCircle2,
      color: 'text-emerald-700',
      bg: 'bg-emerald-50/70',
      border: 'border-emerald-200',
      subtitle: 'Match >= 68% (ArcFace)',
      filterKey: 'confirmed'
    },
    {
      label: 'Needs Review',
      value: stats.needs_review_count,
      icon: AlertCircle,
      color: 'text-amber-700',
      bg: 'bg-amber-50/70',
      border: 'border-amber-200',
      badge: stats.needs_review_count > 0 ? 'Action Req' : undefined,
      subtitle: 'Match 50% - 68%',
      filterKey: 'needs_review'
    },
    {
      label: 'Unmarked / Pending',
      value: stats.unmarked_count,
      icon: Clock,
      color: 'text-blue-700',
      bg: 'bg-blue-50/70',
      border: 'border-blue-200',
      subtitle: 'Awaiting detection',
      filterKey: 'unmarked'
    },
    {
      label: 'Absent',
      value: stats.absent_count,
      icon: XCircle,
      color: 'text-rose-700',
      bg: 'bg-rose-50/70',
      border: 'border-rose-200',
      subtitle: 'Not detected in period',
      filterKey: 'absent'
    },
    {
      label: 'Spoof Attempts Blocked',
      value: stats.spoof_attempts_blocked,
      icon: ShieldAlert,
      color: 'text-red-700',
      bg: 'bg-red-50/70',
      border: 'border-red-200',
      subtitle: 'MiniFASNet Liveness',
      filterKey: 'spoof'
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
      {cards.map((c, i) => {
        const Icon = c.icon;
        return (
          <div
            key={i}
            onClick={() => onFilterSelect && onFilterSelect(c.filterKey)}
            className={`p-3.5 rounded-xl border ${c.bg} ${c.border} shadow-2xs hover:shadow-xs transition-all cursor-pointer flex flex-col justify-between`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-semibold text-slate-600 truncate">{c.label}</span>
              <Icon className={`w-4 h-4 ${c.color}`} />
            </div>

            <div className="flex items-baseline justify-between">
              <span className={`text-2xl font-bold tracking-tight ${c.color}`}>
                {c.value}
              </span>
              {c.badge && (
                <span className="text-[10px] uppercase tracking-wider font-bold bg-amber-200/80 text-amber-900 px-1.5 py-0.5 rounded">
                  {c.badge}
                </span>
              )}
            </div>

            {c.subtitle && (
              <p className="text-[10px] text-slate-400 font-medium mt-1 truncate">
                {c.subtitle}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
};
