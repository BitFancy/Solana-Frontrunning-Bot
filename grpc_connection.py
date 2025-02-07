import grpc
from grpc_geyser.geyser_pb2 import (
    SubscribeRequestFilterTransactions,
    SubscribeRequestFilterSlots,
    SubscribeRequest,
    SubscribeUpdate,
    CommitmentLevel,
    GetLatestBlockhashRequest,
)
from grpc_geyser.geyser_pb2_grpc import GeyserStub
from constants import GEYSER_ADDRESS, RPC_TOKEN

metadata = [("x-token", RPC_TOKEN)]


class HeaderInterceptor(
    grpc.UnaryStreamClientInterceptor, grpc.StreamStreamClientInterceptor
):

    def __init__(self, metadata):
        self.metadata = metadata

    def intercept_stream_stream(
        self, continuation, client_call_details, request_iterator
    ):
        new_details = client_call_details._replace(metadata=self.metadata)
        return continuation(new_details, request_iterator)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        new_details = client_call_details._replace(metadata=self.metadata)
        return continuation(new_details, request)


class GRPCConnection:

    def parse_response(self, response):

        if not isinstance(response, SubscribeUpdate):
            print(f"Error: response type: {type(response)}")
            return

        if response.HasField("transaction"):
            txn = response.transaction.transaction
            return txn

    def request_generator(self):
        while True:
            request = SubscribeRequest(
                transactions={
                    "default": SubscribeRequestFilterTransactions(
                        failed=False,
                        vote=False,
                        account_include=[
                            "CkUZV387xnoGpF7wC2moMa6mPmAgCvTT4pWgzq4M9fCD"
                        ],
                    )
                },
                slots={
                    "default": SubscribeRequestFilterSlots(filter_by_commitment=True)
                },
                commitment=CommitmentLevel.PROCESSED,
            )
            yield request

    def get_latest_block(self):
        try:

            block_request = GetLatestBlockhashRequest(
                commitment=CommitmentLevel.PROCESSED
            )
            return self.stub.GetLatestBlockhash(
                block_request,
                metadata=metadata,
            )

        except Exception as e:
            print("latest_block error", e)

    def subscribe_to_mempool(self, channel):
        try:
            response_stream = self.stub.Subscribe(
                self.request_generator(),
                metadata=metadata,
            )

            return response_stream
        except grpc.RpcError as e:
            print(f"Error gRPC: {e.details()}")
            print(f"Error code: {e.code()}")

    def connect(self):
        try:
            return self.subscribe_to_mempool(self.channel)
        except KeyboardInterrupt:
            print("The connection closed by user.")
            self.channel.close()
        except grpc.RpcError as e:
            print(f"Error gRPC: {e.details()}")
            self.channel.close()

    def init(self):
        creds = grpc.ssl_channel_credentials()
        channel = grpc.secure_channel(GEYSER_ADDRESS, creds)

        interceptor = HeaderInterceptor(metadata=metadata)

        self.channel = grpc.intercept_channel(channel, interceptor)
        self.stub = GeyserStub(self.channel)
