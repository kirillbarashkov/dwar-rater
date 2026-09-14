import { MEMBER_STATUS_LABEL, type MemberStatus } from '../../utils/treasury';
import './MemberStatusBadge.css';

interface MemberStatusBadgeProps {
  status?: MemberStatus;
}

export function MemberStatusBadge({ status }: MemberStatusBadgeProps) {
  if (!status || status === 'active') return null;
  return (
    <span className={`member-status member-status-${status}`}>
      ⚠ {MEMBER_STATUS_LABEL[status]}
    </span>
  );
}