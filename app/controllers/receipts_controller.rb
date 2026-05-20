class ReceiptsController < ApplicationController
  before_action :set_group

  def show
    @memberships = @group.memberships.includes(:user)
    pdf = build_pdf

    send_data pdf.render,
              filename: receipt_filename,
              type: "application/pdf",
              disposition: "inline"
  end

  private

  def set_group
    @group = current_user.carpool_groups
                         .includes(:car, :trip, memberships: :user)
                         .find(params[:carpool_group_id])
  end

  def receipt_filename
    month_label = @group.month.strftime("%B_%Y")
    "receipt_#{@group.name.parameterize}_#{month_label}.pdf"
  end

  def build_pdf
    group   = @group
    trips   = group.trip_logs.sum(:trip_count)
    tally   = group.monthly_tally

    Prawn::Document.new do |pdf|
      pdf.font_families.update("Helvetica" => { normal: "Helvetica", bold: "Helvetica-Bold" })
      pdf.font "Helvetica"

      pdf.text "Carpool Receipt — #{group.name}", size: 18, style: :bold
      pdf.move_down 4
      pdf.text "Month: #{group.month.strftime('%B %Y')}"
      pdf.text "Car: #{group.car.name} (R#{group.car.cost_per_km}/km)"
      pdf.text "Route: #{group.trip.name} (#{group.trip.distance_km} km per trip)"
      pdf.text "Total Trips: #{trips}"
      pdf.text "Total Cost: R#{'%.2f' % tally}"
      pdf.text "Generated: #{Time.current.strftime('%Y-%m-%d %H:%M')}"

      pdf.move_down 12
      pdf.stroke_horizontal_rule
      pdf.move_down 12

      pdf.text "Member Breakdown", style: :bold
      pdf.move_down 6

      rows = group.memberships.includes(:user).map do |m|
        amount = group.monthly_tally * m.cost_split_percentage
        [ m.user.display_name, "#{'%.0f' % (m.cost_split_percentage * 100)}%", "R#{'%.2f' % amount}" ]
      end

      Prawn::Table.new(
        [ [ "Member", "Share", "Amount" ] ] + rows,
        pdf,
        header: true,
        column_widths: [ 280, 100, 120 ],
        cell_style: { padding: [ 6, 8 ] }
      ) do |t|
        t.row(0).font_style = :bold
        t.row(0).background_color = "EEEEEE"
      end.draw

      pdf.move_down 12
      pdf.stroke_horizontal_rule
      pdf.move_down 6
      pdf.text "Total accounted: R#{'%.2f' % tally}", style: :bold
    end
  end
end
