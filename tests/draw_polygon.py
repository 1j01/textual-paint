from textual.geometry import Offset
from textual.pilot import Pilot
from textual.widget import Widget
from textual_paint.paint import PaintApp


async def draw_polygon(pilot: Pilot[None]):
    tool_buttons = pilot.app.query("ToolsBox Button")
    color_buttons = pilot.app.query("ColorsBox Button")
    for button in tool_buttons:
        if button.tooltip == "Polygon":
            polygon_tool_button = button
            break
    else:
        raise Exception("Couldn't find Polygon tool button")

    async def clickity(button: Widget) -> None:
        button.add_class("to_click")
        await pilot.pause(1.0) # for good luck
        await pilot.click(".to_click")
        button.remove_class("to_click")
        await pilot.pause(1.0) # for good luck

    await clickity(polygon_tool_button)
    await pilot.click("Canvas", offset=Offset(2, 2))
    await pilot.click("Canvas", offset=Offset(2, 20))
    await pilot.click("Canvas", offset=Offset(30, 20))
    await pilot.click("Canvas", offset=Offset(30, 2))
    await pilot.click("Canvas", offset=Offset(2, 2)) # end by clicking on the start point
    # await clickity(color_buttons[16]) # red
    # await pilot.click("Canvas", offset=Offset(10, 5))
    # await pilot.click("Canvas", offset=Offset(10, 9))
    # await pilot.click("Canvas", offset=Offset(10, 9))
    # await pilot.click("Canvas", offset=Offset(1, 5))
    # await pilot.click("Canvas", offset=Offset(1, 5)) # end by double clicking
    # await clickity(color_buttons[17]) # yellow
    # await pilot.click("Canvas", offset=Offset(10, 13))
    # await pilot.click("Canvas", offset=Offset(15, 13))
    # await pilot.click("Canvas", offset=Offset(12, 16)) # don't end, leave as polyline

if __name__ == "__main__":
    PaintApp().run(auto_pilot=draw_polygon)
