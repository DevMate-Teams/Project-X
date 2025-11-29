"""
Engagement Analytics Utility - Calculate and aggregate user engagement metrics over time periods

This module provides efficient database-level aggregation for visualizing log engagement trends.
"""
from django.db.models import Count, Q, F, Sum, Prefetch
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.utils import timezone
from datetime import timedelta, date
from logs.models import Log, Reaction, Comment


def get_engagement_over_time(user_info, start_date=None, end_date=None, granularity='day'):
    """
    Calculate engagement metrics for a user's logs over a specified time period.
    
    Metrics are calculated based on LOG CREATION DATE - i.e., for each period,
    we count logs created in that period and ALL engagement (reactions/comments)
    those logs have received (regardless of when the engagement occurred).
    
    Args:
        user_info: userinfo object (the user whose engagement we're analyzing)
        start_date: Start of the date range (date object, defaults to 30 days ago)
        end_date: End of the date range (date object, defaults to today)
        granularity: 'day', 'week', or 'month' - how to group the data
    
    Returns:
        dict: {
            'labels': ['2025-11-01', '2025-11-02', ...],
            'logs': [5, 3, 8, ...],
            'reactions': [12, 5, 20, ...],
            'comments': [3, 1, 5, ...],
            'total_engagement': [15, 6, 25, ...],
            'summary': {
                'total_logs': 100,
                'total_reactions': 250,
                'total_comments': 75,
                'avg_engagement_per_log': 3.25
            }
        }
    """
    # Set default date range (last 30 days)
    if end_date is None:
        end_date = timezone.now().date()
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    
    # Ensure dates are date objects
    if hasattr(start_date, 'date'):
        start_date = start_date.date()
    if hasattr(end_date, 'date'):
        end_date = end_date.date()
    
    # Use annotation for counts - single query with aggregated counts
    # This is more efficient than prefetch + iteration with .count()
    logs_in_range = Log.objects.filter(
        user=user_info,
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    ).annotate(
        reaction_count=Count('reactions', distinct=True),
        comment_count=Count('comments', distinct=True)
    ).only('timestamp').order_by('timestamp')
    
    # Build data map by aggregating per period
    data_map = {}
    
    for log in logs_in_range:
        # Determine the period key based on granularity
        log_date = log.timestamp.date()
        
        if granularity == 'day':
            period_key = log_date.strftime('%Y-%m-%d')
        elif granularity == 'week':
            # Get Monday of the week
            week_start = log_date - timedelta(days=log_date.weekday())
            period_key = week_start.strftime('%Y-%m-%d')
        else:  # month
            period_key = date(log_date.year, log_date.month, 1).strftime('%Y-%m-%d')
        
        # Initialize period if not exists
        if period_key not in data_map:
            data_map[period_key] = {
                'logs': 0,
                'reactions': 0,
                'comments': 0
            }
        
        # Count this log and use annotated counts (no extra queries)
        data_map[period_key]['logs'] += 1
        data_map[period_key]['reactions'] += log.reaction_count
        data_map[period_key]['comments'] += log.comment_count
    
    # Generate all period keys in range
    labels = []
    logs_data = []
    reactions_data = []
    comments_data = []
    total_engagement_data = []
    
    if granularity == 'day':
        current_date = start_date
        while current_date <= end_date:
            period_key = current_date.strftime('%Y-%m-%d')
            data = data_map.get(period_key, {'logs': 0, 'reactions': 0, 'comments': 0})
            
            labels.append(period_key)
            logs_data.append(data['logs'])
            reactions_data.append(data['reactions'])
            comments_data.append(data['comments'])
            total_engagement_data.append(data['reactions'] + data['comments'])
            
            current_date += timedelta(days=1)
            
    elif granularity == 'week':
        # Start from Monday of start_date's week
        current_date = start_date - timedelta(days=start_date.weekday())
        while current_date <= end_date:
            period_key = current_date.strftime('%Y-%m-%d')
            data = data_map.get(period_key, {'logs': 0, 'reactions': 0, 'comments': 0})
            
            labels.append(period_key)
            logs_data.append(data['logs'])
            reactions_data.append(data['reactions'])
            comments_data.append(data['comments'])
            total_engagement_data.append(data['reactions'] + data['comments'])
            
            current_date += timedelta(weeks=1)
            
    else:  # month
        # Start from first day of start_date's month
        current_date = date(start_date.year, start_date.month, 1)
        while current_date <= end_date:
            period_key = current_date.strftime('%Y-%m-%d')
            data = data_map.get(period_key, {'logs': 0, 'reactions': 0, 'comments': 0})
            
            labels.append(period_key)
            logs_data.append(data['logs'])
            reactions_data.append(data['reactions'])
            comments_data.append(data['comments'])
            total_engagement_data.append(data['reactions'] + data['comments'])
            
            # Move to next month
            if current_date.month == 12:
                current_date = date(current_date.year + 1, 1, 1)
            else:
                current_date = date(current_date.year, current_date.month + 1, 1)
    
    # Calculate summary statistics
    total_logs = sum(logs_data)
    total_reactions = sum(reactions_data)
    total_comments = sum(comments_data)
    avg_engagement = round((total_reactions + total_comments) / max(total_logs, 1), 2)
    
    return {
        'labels': labels,
        'logs': logs_data,
        'reactions': reactions_data,
        'comments': comments_data,
        'total_engagement': total_engagement_data,
        'summary': {
            'total_logs': total_logs,
            'total_reactions': total_reactions,
            'total_comments': total_comments,
            'avg_engagement_per_log': avg_engagement
        }
    }


def get_engagement_breakdown(user_info, start_date=None, end_date=None):
    """
    Get detailed breakdown of engagement types (reaction emojis, comment vs reply)
    
    Args:
        user_info: userinfo object
        start_date: Start of date range
        end_date: End of date range
    
    Returns:
        dict: {
            'reaction_breakdown': {'❤️': 50, '🚀': 30, '💡': 15, '😢': 5},
            'comment_vs_reply': {'comments': 60, 'replies': 40},
            'top_performing_logs': [...]
        }
    """
    if end_date is None:
        end_date = timezone.now().date()
    if start_date is None:
        start_date = end_date - timedelta(days=30)
    
    # Ensure dates are date objects
    if hasattr(start_date, 'date'):
        start_date = start_date.date()
    if hasattr(end_date, 'date'):
        end_date = end_date.date()
    
    # Use subquery for log IDs instead of materializing to list
    log_filter = Q(
        user=user_info,
        timestamp__date__gte=start_date,
        timestamp__date__lte=end_date
    )
    
    # Reaction breakdown by emoji - single aggregated query
    reaction_counts = Reaction.objects.filter(
        mindlog__user=user_info,
        mindlog__timestamp__date__gte=start_date,
        mindlog__timestamp__date__lte=end_date
    ).values('emoji').annotate(
        count=Count('id')
    )
    reaction_breakdown = {item['emoji']: item['count'] for item in reaction_counts}
    
    # Comment vs Reply breakdown - use conditional aggregation in single query
    comment_stats = Comment.objects.filter(
        mindlog__user=user_info,
        mindlog__timestamp__date__gte=start_date,
        mindlog__timestamp__date__lte=end_date
    ).aggregate(
        comments=Count('id', filter=Q(parent_comment__isnull=True)),
        replies=Count('id', filter=Q(parent_comment__isnull=False))
    )
    comments_count = comment_stats['comments'] or 0
    replies_count = comment_stats['replies'] or 0
    
    # Top performing logs - single query with annotations
    top_logs = Log.objects.filter(log_filter).annotate(
        reaction_total=Count('reactions', distinct=True),
        comment_total=Count('comments', distinct=True)
    ).only('sig', 'content', 'timestamp').order_by('-reaction_total', '-comment_total')[:5]
    
    top_logs_data = [
        {
            'sig': log.sig,
            'content': log.content[:100],
            'reactions': log.reaction_total,
            'comments': log.comment_total,
            'engagement': log.reaction_total + log.comment_total,
            'timestamp': log.timestamp.strftime('%Y-%m-%d')
        }
        for log in top_logs
        if log.reaction_total + log.comment_total > 0
    ]
    
    return {
        'reaction_breakdown': reaction_breakdown,
        'comment_vs_reply': {
            'comments': comments_count,
            'replies': replies_count,
            'total': comments_count + replies_count
        },
        'top_performing_logs': top_logs_data
    }


def get_engagement_comparison(user_info, period='week'):
    """
    Compare engagement between current period and previous period
    
    Args:
        user_info: userinfo object
        period: 'week' or 'month'
    
    Returns:
        dict: {
            'current': {'logs': X, 'reactions': Y, 'comments': Z},
            'previous': {'logs': X, 'reactions': Y, 'comments': Z},
            'change': {'logs': '+10%', 'reactions': '-5%', 'comments': '+25%'}
        }
    """
    today = timezone.now().date()
    
    if period == 'week':
        current_start = today - timedelta(days=6)  # Last 7 days including today
        current_end = today
        previous_start = today - timedelta(days=13)
        previous_end = today - timedelta(days=7)
    else:  # month
        current_start = today - timedelta(days=29)  # Last 30 days including today
        current_end = today
        previous_start = today - timedelta(days=59)
        previous_end = today - timedelta(days=30)
    
    def get_period_stats(start, end):
        """Get engagement stats for logs created in the given period - single query"""
        stats = Log.objects.filter(
            user=user_info,
            timestamp__date__gte=start,
            timestamp__date__lte=end
        ).aggregate(
            log_count=Count('id', distinct=True),
            reaction_count=Count('reactions', distinct=True),
            comment_count=Count('comments', distinct=True)
        )
        
        return {
            'logs': stats['log_count'] or 0,
            'reactions': stats['reaction_count'] or 0,
            'comments': stats['comment_count'] or 0
        }
    
    current = get_period_stats(current_start, current_end)
    previous = get_period_stats(previous_start, previous_end)
    
    def calc_change(curr, prev):
        if prev == 0:
            if curr == 0:
                return '0%'
            return '+∞'
        change = ((curr - prev) / prev) * 100
        sign = '+' if change >= 0 else ''
        return f"{sign}{round(change)}%"
    
    return {
        'current': current,
        'previous': previous,
        'change': {
            'logs': calc_change(current['logs'], previous['logs']),
            'reactions': calc_change(current['reactions'], previous['reactions']),
            'comments': calc_change(current['comments'], previous['comments'])
        },
        'period': period,
        'current_range': f"{current_start.strftime('%b %d')} - {current_end.strftime('%b %d')}",
        'previous_range': f"{previous_start.strftime('%b %d')} - {previous_end.strftime('%b %d')}"
    }


def get_engagement_heatmap_data(user_info, year=None):
    """
    Get engagement data formatted for a calendar heatmap visualization
    
    Args:
        user_info: userinfo object
        year: Year to get data for (defaults to current year)
    
    Returns:
        list: [{'date': '2025-01-15', 'logs': 3, 'engagement': 12}, ...]
    """
    if year is None:
        year = timezone.now().year
    
    # Use database-level aggregation with TruncDate for efficient grouping
    # Use distinct=True to avoid count inflation from joins
    from django.db.models.functions import TruncDate
    
    daily_stats = Log.objects.filter(
        user=user_info,
        timestamp__year=year
    ).annotate(
        log_date=TruncDate('timestamp')
    ).values('log_date').annotate(
        logs=Count('id', distinct=True),
        reactions=Count('reactions', distinct=True),
        comments=Count('comments', distinct=True)
    ).order_by('log_date')
    
    # Transform to expected format
    return [
        {
            'date': stat['log_date'].strftime('%Y-%m-%d'),
            'logs': stat['logs'],
            'reactions': stat['reactions'],
            'comments': stat['comments'],
            'engagement': stat['reactions'] + stat['comments']
        }
        for stat in daily_stats
    ]
