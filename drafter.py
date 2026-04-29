from typing import Annotated, Sequence,TypedDict
from langchain_core.messages import BaseMessage, SystemMessage, ToolMessage, HumanMessage, AIMessage
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

doc_content = ""
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

@tool
def update(content: str) -> str:
    """Updates the document with the provided content. Always pass the FULL document, not just changes."""
    global doc_content
    doc_content = content
    return f"Document updated successfully! \nCurrent doc:\n{doc_content}"

@tool
def save(filename:str)->str:
    """Save the doc to textfile and finish the process
        Args: 
            filename: Name of Text file
    """
    global doc_content
    if not filename.endswith(".txt"):
        filename += ".txt"
    try:
        with open(filename, 'w') as file:
            file.write(doc_content)
        print(f"Document is saved to {filename}")
        return "document has been successfully saved!"
    except Exception as e:
        return f"Error saving doc{str(e)}"

tools = [update, save]
model = ChatOllama(model="llama3.1").bind_tools(tools)

def agent(state:AgentState)->AgentState:
    system_prompt = SystemMessage(content="""
    You are drafter, a helpful writing assistant. You help the user update and modify documents.
    1. If the user wants to update the document, use the 'update' tool with the complete updated content as a single string.
    2. If the user wants to save and finish, use the 'save' tool.
    3. Make sure to always show the current document state after modifications.
    4. The document state is tracked via tool responses — refer to those for the latest version.
    """)
    if not state['messages']:
        user_input = input("\nWhat would you like to draft? ")
    else:
        user_input = input("\nWhat would you like to do with the document? ")
    print(f"\nUser: {user_input}")
    user_message = HumanMessage(content=user_input)
    all_messages = [system_prompt] + list(state['messages']) + [user_message]
    
    print(f"\nSending {len(all_messages)} messages to LLM")
    response = model.invoke(all_messages)
    
    if response.content:
        print(f"\nAI: {response.content}")

    if hasattr(response, "tool_calls") and response.tool_calls:
        for tc in response.tool_calls:
            print(f"\nTool call: {tc['name']}({tc['args']})")
    
    return {"messages":list(state["messages"]) + [user_message, response]}

def should_continue(state: AgentState) -> str:
    """Determines if we should continue or end the conversation"""
    messages = state['messages']
    if not messages:
        return "continue"
    for message in reversed(messages):
        if isinstance(message, ToolMessage) and "saved" in message.content.lower():
            return "end"
    return "continue"

def print_messages(messages):
    if not messages:
        return
    last_msg = messages[-1]
    msg_type = type(last_msg).__name__
    print(f"\n Total messages: {len(messages)} | Latest: {msg_type}")
    for message in messages[-3:]:
        if isinstance(message, ToolMessage):
            print()
            print(f"Tool Result: {message.content}")
            print()
graph = StateGraph(AgentState)
graph.add_node("agent", agent)
graph.add_node("tools", ToolNode(tools))
graph.set_entry_point("agent")
graph.add_edge("agent", "tools")
graph.add_conditional_edges(
    "tools",
    should_continue,
    {
        "continue": "agent",
        "end": END
    },
)
app = graph.compile()

# import os
# png_data = app.get_graph().draw_mermaid_png()
# with open("visualize.png", "wb") as f:
#     f.write(png_data)
# print("Graph saved to visualize.png")
# os.startfile("visualize.png") 

def run_agent():
    print("\n Drafter Agent Started!")
    state = {"messages": []}
    for step in app.stream(state, stream_mode="values"):
        if "messages" in step:
            print_messages(step["messages"])
    print("\n Drafter Agent Finished!")
run_agent()