"""
Cost Optimization Hub Page Builder

This module generates HTML pages for the Cost Optimization Hub custom page.
It follows the existing CustomPageBuilder pattern used by other Service Screener
custom pages while providing specialized cost optimization visualizations.
"""

import json
import uuid
from datetime import datetime
from utils.CustomPage.CustomPageBuilder import CustomPageBuilder
from utils.Config import Config
import constants as _C


class COHPageBuilder(CustomPageBuilder):
    """
    Page builder for Cost Optimization Hub
    
    Inherits from CustomPageBuilder to integrate with Service Screener's page generation
    infrastructure while providing specialized cost optimization HTML generation.
    """
    
    def __init__(self, service='coh', reporter=None):
        super().__init__(service, reporter)
        self.hasError = False
        self.error_message = ""
    
    def customPageInit(self):
        """Initialize custom page with error checking"""
        if hasattr(self.data, 'error_messages') and self.data.error_messages:
            self.hasError = True
            self.error_message = "; ".join(self.data.error_messages)
        
        # Check if we have any recommendations
        if not hasattr(self.data, 'recommendations') or not self.data.recommendations:
            if not self.hasError:
                self.hasError = True
                self.error_message = "No cost optimization recommendations found. This may be due to insufficient permissions, service not enabled, or no optimization opportunities available."
        
        # Add Chart.js library for visualizations
        self.addJSLib('https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js')
        self.addCSSLib('https://cdn.jsdelivr.net/npm/datatables.net-bs5@1.11.3/css/dataTables.bootstrap5.min.css')
        self.addJSLib('https://cdn.jsdelivr.net/npm/datatables.net@1.11.3/js/jquery.dataTables.min.js')
        self.addJSLib('https://cdn.jsdelivr.net/npm/datatables.net-bs5@1.11.3/js/dataTables.bootstrap5.min.js')
        
        return
    
    def buildContentSummary_customPage(self):
        """Build summary content for the COH page"""
        if self.hasError:
            return [f"<span class='text-danger'>{self.error_message}</span>"]
        
        if not hasattr(self.data, 'executive_summary') or not self.data.executive_summary:
            return ["<span>No executive summary available</span>"]
        
        summary = self.data.executive_summary
        
        # Create executive summary cards using the framework's pattern
        items = []
        
        # Total savings card
        total_monthly = f"${summary.total_monthly_savings:,.2f}"
        total_annual = f"${summary.total_annual_savings:,.2f}"
        savings_card = f"""
        <div class="info-box bg-success">
            <span class="info-box-icon"><i class="fas fa-dollar-sign"></i></span>
            <div class="info-box-content">
                <span class="info-box-text">Potential Savings</span>
                <span class="info-box-number">{total_monthly}/month</span>
                <span class="info-box-more">{total_annual}/year</span>
            </div>
        </div>
        """
        items.append([savings_card, ''])
        
        # Total recommendations card
        recommendations_card = f"""
        <div class="info-box bg-info">
            <span class="info-box-icon"><i class="fas fa-lightbulb"></i></span>
            <div class="info-box-content">
                <span class="info-box-text">Recommendations</span>
                <span class="info-box-number">{summary.total_recommendations}</span>
                <span class="info-box-more">optimization opportunities</span>
            </div>
        </div>
        """
        items.append([recommendations_card, ''])
        
        # High priority recommendations card
        high_priority_card = f"""
        <div class="info-box bg-warning">
            <span class="info-box-icon"><i class="fas fa-exclamation-triangle"></i></span>
            <div class="info-box-content">
                <span class="info-box-text">High Priority</span>
                <span class="info-box-number">{summary.high_priority_count}</span>
                <span class="info-box-more">immediate actions</span>
            </div>
        </div>
        """
        items.append([high_priority_card, ''])
        
        # Data freshness card
        freshness = summary.data_freshness.strftime('%Y-%m-%d %H:%M UTC')
        freshness_card = f"""
        <div class="info-box bg-secondary">
            <span class="info-box-icon"><i class="fas fa-clock"></i></span>
            <div class="info-box-content">
                <span class="info-box-text">Last Updated</span>
                <span class="info-box-number" style="font-size: 14px;">{freshness}</span>
                <span class="info-box-more">data freshness</span>
            </div>
        </div>
        """
        items.append([freshness_card, ''])
        
        output = []
        output.append(self.generateRowWithCol(size=3, items=items, rowHtmlAttr="data-context='executiveSummary'"))
        
        return output
    
    def buildContentDetail_customPage(self):
        """Build detailed content for the COH page"""
        if self.hasError:
            return []
        
        output = []
        
        # Build charts section
        charts_section = self._build_charts_section()
        output.extend(charts_section)
        
        # Build recommendations by priority
        priority_sections = self._build_priority_sections()
        output.extend(priority_sections)
        
        # Build recommendations by category
        category_sections = self._build_category_sections()
        output.extend(category_sections)
        
        return output
    
    def _build_charts_section(self):
        """Build charts section using the framework's chart methods"""
        output = []
        
        if not hasattr(self.data, 'get_recommendations_by_priority'):
            return output
        
        # Get data for charts
        recommendations_by_priority = self.data.get_recommendations_by_priority()
        recommendations_by_category = self.data.get_recommendations_by_category()
        
        items = []
        
        # Priority distribution chart
        priority_data = {}
        for priority, recs in recommendations_by_priority.items():
            priority_data[priority.title()] = len(recs)
        
        if priority_data:
            chart_html = self.generateDonutPieChart(priority_data, 'priority', 'doughnut')
            card = self.generateCard(
                pid=self.getHtmlId('priority_chart'),
                html=chart_html,
                cardClass='primary',
                title='<i class="fas fa-chart-pie"></i> Recommendations by Priority',
                collapse=True
            )
            items.append([card, ''])
        
        # Category distribution chart
        category_data = {}
        for category, recs in recommendations_by_category.items():
            if recs:  # Only include categories with recommendations
                category_data[category.title()] = len(recs)
        
        if category_data:
            chart_html = self.generateDonutPieChart(category_data, 'category', 'pie')
            card = self.generateCard(
                pid=self.getHtmlId('category_chart'),
                html=chart_html,
                cardClass='info',
                title='<i class="fas fa-chart-pie"></i> Recommendations by Category',
                collapse=True
            )
            items.append([card, ''])
        
        if items:
            output.append(self.generateRowWithCol(size=6, items=items, rowHtmlAttr="data-context='charts'"))
        
        return output
    
    def _build_priority_sections(self):
        """Build sections organized by priority level"""
        output = []
        
        if not hasattr(self.data, 'get_recommendations_by_priority'):
            return output
        
        recommendations_by_priority = self.data.get_recommendations_by_priority()
        
        priority_config = {
            'high': {'badge': 'danger', 'icon': 'fas fa-exclamation-triangle', 'title': 'High Priority Recommendations'},
            'medium': {'badge': 'warning', 'icon': 'fas fa-exclamation-circle', 'title': 'Medium Priority Recommendations'},
            'low': {'badge': 'info', 'icon': 'fas fa-info-circle', 'title': 'Low Priority Recommendations'}
        }
        
        for priority in ['high', 'medium', 'low']:
            recommendations = recommendations_by_priority.get(priority, [])
            if not recommendations:
                continue
            
            config = priority_config[priority]
            
            # Create table for this priority level
            table_html = self._create_recommendations_table(recommendations)
            
            card_title = f"<i class='{config['icon']}'></i> {config['title']} <span class='badge badge-{config['badge']}'>{len(recommendations)}</span>"
            
            card = self.generateCard(
                pid=self.getHtmlId(f"priority_{priority}"),
                html=table_html,
                cardClass='primary',
                title=card_title,
                titleBadge='',
                collapse=True,
                noPadding=False
            )
            
            items = [[card, '']]
            output.append(self.generateRowWithCol(12, items, "data-context='priorityTable'"))
        
        return output
    
    def _build_category_sections(self):
        """Build sections organized by service category"""
        output = []
        
        if not hasattr(self.data, 'get_recommendations_by_category'):
            return output
        
        recommendations_by_category = self.data.get_recommendations_by_category()
        
        category_config = {
            'compute': {'icon': 'fas fa-server', 'title': 'Compute Optimization'},
            'storage': {'icon': 'fas fa-hdd', 'title': 'Storage Optimization'},
            'database': {'icon': 'fas fa-database', 'title': 'Database Optimization'},
            'commitment': {'icon': 'fas fa-handshake', 'title': 'Commitment Discounts'},
            'general': {'icon': 'fas fa-cogs', 'title': 'General Optimization'}
        }
        
        for category, recommendations in recommendations_by_category.items():
            if not recommendations:
                continue
            
            config = category_config.get(category, {'icon': 'fas fa-cogs', 'title': category.title()})
            
            # Calculate category totals
            total_monthly = sum(rec.monthly_savings for rec in recommendations)
            
            # Create table for this category
            table_html = self._create_recommendations_table(recommendations)
            
            card_title = f"<i class='{config['icon']}'></i> {config['title']} <span class='badge badge-success'>${total_monthly:,.2f}/month</span>"
            
            card = self.generateCard(
                pid=self.getHtmlId(f"category_{category}"),
                html=table_html,
                cardClass='info',
                title=card_title,
                titleBadge='',
                collapse=True,
                noPadding=False
            )
            
            items = [[card, '']]
            output.append(self.generateRowWithCol(12, items, "data-context='categoryTable'"))
        
        return output
    
    def _create_recommendations_table(self, recommendations):
        """Create a table of recommendations using framework patterns"""
        if not recommendations:
            return "<p class='text-muted'>No recommendations available</p>"
        
        # Create table header
        table_html = """
        <div class="table-responsive">
            <table class="table table-bordered table-hover table-striped">
                <thead class="thead-light">
                    <tr>
                        <th>Priority</th>
                        <th>Service</th>
                        <th>Title</th>
                        <th>Monthly Savings</th>
                        <th>Annual Savings</th>
                        <th>Implementation Effort</th>
                        <th>Confidence</th>
                        <th>Resources</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Add rows for each recommendation
        for rec in recommendations:
            priority_badge = f"<span class='badge badge-{self._get_priority_badge_class(rec.priority_level)}'>{rec.priority_level.title()}</span>"
            effort_badge = f"<span class='badge badge-{self._get_effort_badge_class(rec.implementation_effort)}'>{rec.implementation_effort.title()}</span>"
            confidence_badge = f"<span class='badge badge-{self._get_confidence_badge_class(rec.confidence_level)}'>{rec.confidence_level.title()}</span>"
            
            table_html += f"""
                <tr>
                    <td>{priority_badge}</td>
                    <td>{rec.service.upper()}</td>
                    <td>
                        <strong>{rec.title}</strong><br>
                        <small class="text-muted">{rec.description[:100]}{'...' if len(rec.description) > 100 else ''}</small>
                    </td>
                    <td>${rec.monthly_savings:,.2f}</td>
                    <td>${rec.annual_savings:,.2f}</td>
                    <td>{effort_badge}</td>
                    <td>{confidence_badge}</td>
                    <td>{rec.resource_count}</td>
                </tr>
            """
        
        table_html += """
                </tbody>
            </table>
        </div>
        """
        
        return table_html
    
    def _get_priority_badge_class(self, priority):
        """Get Bootstrap badge class for priority level"""
        return {
            'high': 'danger',
            'medium': 'warning', 
            'low': 'info'
        }.get(priority, 'secondary')
    
    def _get_effort_badge_class(self, effort):
        """Get Bootstrap badge class for implementation effort"""
        return {
            'low': 'success',
            'medium': 'warning',
            'high': 'danger'
        }.get(effort, 'secondary')
    
    def _get_confidence_badge_class(self, confidence):
        """Get Bootstrap badge class for confidence level"""
        return {
            'high': 'success',
            'medium': 'warning',
            'low': 'danger'
        }.get(confidence, 'secondary')